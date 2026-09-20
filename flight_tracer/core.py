# flight_tracer/core.py
"""Fetch and process ADS-B Exchange flight traces.

Field order and the ``flags`` bitmask follow ADS-B Exchange's own
documentation (https://www.adsbexchange.com/version-2-api/) rather than a
guess, so flight-leg boundaries come straight from their detector instead of
a time-gap heuristic:

    flags & 1  ->  position is stale (no update for 20s before this one)
    flags & 2  ->  start of a new leg (their own landing/takeoff split)
    flags & 4  ->  vertical rate is geometric, not barometric
    flags & 8  ->  altitude is geometric, not barometric
"""

import os
import warnings
from datetime import timedelta
from io import BytesIO

import boto3
import geopandas as gpd
import pandas as pd
import pytz
import requests
from shapely.geometry import LineString

warnings.filterwarnings("ignore", category=UserWarning, message="Column names longer than 10 characters")

# Raw trace array field order, per ADS-B Exchange / readsb.
TRACE_COLUMNS = [
    "seconds_after_timestamp",
    "lat",
    "lon",
    "altitude",
    "ground_speed",
    "track",
    "flags",
    "vertical_rate",
    "aircraft_details",
    "position_source",
    "geom_altitude",
    "geom_vertical_rate",
    "indicated_airspeed",
    "roll",
]

# None means UTC-only: no point_time_local column, nothing to get out of
# sync. Aviation data -- ADS-B, ATC, pilots -- is UTC-native, and a global
# newsroom has no reason to default to any one city's clock. Local time is
# opt-in via the timezone argument (see identify.resolve_timezone).
DEFAULT_TIMEZONE = None


class FlightTracer:
    def __init__(self, aircraft_ids=None, meta_url=None, aws_creds=None, aws_profile=None):
        """
        Initialize with a list of aircraft_ids (ICAO hex codes) or a metadata URL.
        Optionally pass aws_creds as a dict with keys:
          'aws_access_key_id' and 'aws_secret_access_key'.
        Alternatively, pass aws_profile to use a specific AWS CLI profile.
        """
        if meta_url:
            meta_df = pd.read_json(meta_url)
            self.aircraft_ids = meta_df["icao"].str.strip().str.lower().tolist()
            self.meta_df = meta_df
        elif aircraft_ids:
            self.aircraft_ids = [ac.strip().lower() for ac in aircraft_ids]
            self.meta_df = None
        else:
            raise ValueError("Either aircraft_ids or meta_url must be provided")

        if aws_profile:
            session = boto3.Session(profile_name=aws_profile)
            self.s3_client = session.client("s3")
        elif aws_creds and aws_creds.get("aws_access_key_id"):
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=aws_creds.get("aws_access_key_id"),
                aws_secret_access_key=aws_creds.get("aws_secret_access_key"),
            )
        else:
            self.s3_client = None

    # ------------------------------------------------------------------
    # Fetching
    # ------------------------------------------------------------------

    def generate_urls(self, start_date, end_date, recent=False):
        """Generate ADS-B Exchange URLs for each aircraft.

        Parameters:
        - start_date (date): Start of the date range. Ignored if recent=True.
        - end_date (date): End of the date range. Ignored if recent=True.
        - recent (bool): If True, fetches only the most recent trace (roughly
          the last few hours to a few days of coverage) instead of a
          specific historical date. This is the breaking-news path: use it
          when you don't know the date yet.

        Returns:
        - List of tuples (url, icao)
        """
        base_url_recent = "https://globe.adsbexchange.com/data/traces/"
        base_url_historical = "https://globe.adsbexchange.com/globe_history/"

        urls = []
        for icao in self.aircraft_ids:
            icao_suffix = icao[-2:]

            if recent:
                url = f"{base_url_recent}{icao_suffix}/trace_full_{icao}.json"
                urls.append((url, icao))
            else:
                delta = timedelta(days=1)
                current_date = start_date
                while current_date <= end_date:
                    year = current_date.strftime("%Y")
                    month = current_date.strftime("%m")
                    day = current_date.strftime("%d")
                    url = f"{base_url_historical}{year}/{month}/{day}/traces/{icao_suffix}/trace_full_{icao}.json"
                    urls.append((url, icao))
                    current_date += delta

        return urls

    def fetch_trace_data(self, url, icao):
        """Fetch and return a raw trace DataFrame from a given URL, or None."""
        headers = {"Referer": f"https://globe.adsbexchange.com/?icao={icao}"}
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            return None

        data = response.json()
        if not data or "trace" not in data or not data["trace"]:
            return None

        trace_df = pd.DataFrame(data["trace"], columns=TRACE_COLUMNS)
        trace_df["registration"] = data.get("r")
        trace_df["model"] = data.get("t")
        trace_df["desc"] = data.get("desc")
        trace_df["owner_op"] = data.get("ownOp")
        trace_df["icao"] = icao

        base_time = pd.to_datetime(data["timestamp"], unit="s", utc=True)
        trace_df["point_time_utc"] = base_time + pd.to_timedelta(
            pd.to_numeric(trace_df["seconds_after_timestamp"], errors="coerce"), unit="s"
        )
        return trace_df

    def get_traces(self, start_date=None, end_date=None, recent=False):
        """
        Fetch trace data from ADS-B Exchange.

        Parameters:
        - start_date, end_date (date or None): Date range. Ignored if recent=True.
        - recent (bool): If True, fetches the most recent trace instead of a
          historical date range.

        Returns:
        - DataFrame containing all collected raw flight traces.
        """
        urls = self.generate_urls(start_date, end_date, recent=recent)
        traces = []

        for url, icao in urls:
            print(f"Fetching: {url}")
            trace_df = self.fetch_trace_data(url, icao)
            if trace_df is not None and not trace_df.empty:
                traces.append(trace_df)
                print(f"  found {len(trace_df):,} points for {icao}")
            else:
                print(f"  no data for {icao}")

        if traces:
            return pd.concat(traces, ignore_index=True).sort_values("point_time_utc").reset_index(drop=True)

        print("No trace data collected.")
        return pd.DataFrame()

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def process_flight_data(self, df, filter_ground=True, timezone=DEFAULT_TIMEZONE):
        """Turn a raw trace DataFrame into a structured GeoDataFrame.

        Flight legs come straight from ADS-B Exchange's own `flags & 2`
        marker (their landing/takeoff detector), not a configurable time-gap
        guess, so there's nothing to tune here.

        Parameters:
        - df: raw trace DataFrame, as returned by get_traces().
        - filter_ground: drop points where altitude == "ground".
        - timezone: IANA zone name, or None (default) to stay UTC-only. When
          set, adds a `point_time_local` column alongside `point_time_utc`
          -- UTC is never dropped, so a local time is always paired with the
          zone-proof original rather than replacing it. Resolve "auto" via
          identify.resolve_timezone() before calling this.

        Returns a GeoDataFrame of points.
        """
        if df.empty:
            return gpd.GeoDataFrame()

        df = df.sort_values(["icao", "point_time_utc"]).reset_index(drop=True)

        flags = pd.to_numeric(df["flags"], errors="coerce").fillna(0).astype(int)
        df["is_stale"] = (flags & 1) > 0
        df["new_leg"] = (flags & 2) > 0
        df["vertical_rate_is_geometric"] = (flags & 4) > 0
        df["altitude_is_geometric"] = (flags & 8) > 0

        # The very first point of a trace always starts leg 1, whether or not
        # ADS-B Exchange flagged it.
        df.loc[df.groupby("icao").head(1).index, "new_leg"] = False
        df["leg_id"] = df.groupby("icao")["new_leg"].cumsum() + 1

        # 'aircraft_details' only arrives on rows where something changed, so
        # forward-fill it to know the callsign at every point.
        details = df["aircraft_details"].apply(lambda d: d if isinstance(d, dict) else {})
        df["call_sign"] = details.apply(lambda d: d.get("flight")).apply(
            lambda v: v.strip() if isinstance(v, str) else v
        )
        df["call_sign"] = df.groupby("icao")["call_sign"].ffill().fillna("UNKNOWN")
        df["squawk"] = details.apply(lambda d: d.get("squawk"))
        df["squawk"] = df.groupby("icao")["squawk"].ffill()
        df["emergency"] = details.apply(lambda d: d.get("emergency"))

        df["flight_leg"] = df["call_sign"] + "_leg" + df["leg_id"].astype(str)

        if timezone:
            try:
                tz = pytz.timezone(timezone)
            except Exception as exc:
                raise ValueError(f"Invalid timezone '{timezone}': {exc}")
            df["point_time_local"] = df["point_time_utc"].dt.tz_convert(tz)

        if filter_ground:
            df = df.loc[df["altitude"] != "ground"].copy()

        numeric_cols = [
            "altitude", "ground_speed", "track", "vertical_rate",
            "geom_altitude", "geom_vertical_rate", "indicated_airspeed", "roll",
        ]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        output_columns = [
            "point_time_utc", "point_time_local",
            "lat", "lon", "altitude", "altitude_is_geometric",
            "ground_speed", "indicated_airspeed", "track", "vertical_rate",
            "vertical_rate_is_geometric", "roll",
            "icao", "registration", "model", "desc", "owner_op",
            "call_sign", "squawk", "emergency",
            "leg_id", "flight_leg", "position_source", "is_stale",
        ]
        output_columns = [c for c in output_columns if c in df.columns]

        return gpd.GeoDataFrame(
            df[output_columns],
            geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        ).set_crs(epsg=4326)

    def create_linestrings(self, gdf, flight_leg_column="flight_leg", point_time_column="point_time_utc"):
        """Collapse a points GeoDataFrame into one LineString per flight leg."""
        if gdf.empty:
            return gpd.GeoDataFrame()

        legs = []
        for flight_leg, group in gdf.groupby(flight_leg_column):
            group = group.sort_values(point_time_column)
            points = list(group.geometry)
            geometry = LineString(points) if len(points) > 1 else points[0]

            legs.append({
                flight_leg_column: flight_leg,
                "icao": group["icao"].iloc[0] if "icao" in group.columns else None,
                "call_sign": group["call_sign"].iloc[0] if "call_sign" in group.columns else None,
                "leg_id": group["leg_id"].iloc[0] if "leg_id" in group.columns else None,
                "start_time_utc": group[point_time_column].iloc[0],
                "end_time_utc": group[point_time_column].iloc[-1],
                "num_points": len(group),
                "geometry": geometry,
            })

        return gpd.GeoDataFrame(legs, crs=gdf.crs)

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def write_outputs(self, gdf, output_dir, formats=("csv", "geojson")):
        """Write points + line outputs to one directory in one call.

        No "raw", "processed" or "exported" chain to remember — this is the
        only save step. Returns a dict of {kind: path} for what was written.
        """
        os.makedirs(output_dir, exist_ok=True)
        gdf_lines = self.create_linestrings(gdf)
        written = {}

        if "csv" in formats:
            csv_path = os.path.join(output_dir, "trace.csv")
            gdf.drop(columns="geometry").to_csv(csv_path, index=False)
            written["csv"] = csv_path

        if "geojson" in formats:
            points_path = os.path.join(output_dir, "points.geojson")
            line_path = os.path.join(output_dir, "line.geojson")
            gdf.to_file(points_path, driver="GeoJSON")
            if not gdf_lines.empty:
                gdf_lines.to_file(line_path, driver="GeoJSON")
            written["points_geojson"] = points_path
            written["line_geojson"] = line_path

        if "shp" in formats:
            shp_dir = os.path.join(output_dir, "shp")
            os.makedirs(shp_dir, exist_ok=True)
            points_path = os.path.join(shp_dir, "points.shp")
            line_path = os.path.join(shp_dir, "lines.shp")
            gdf_shp = gdf.copy()
            for col in gdf_shp.columns:
                if pd.api.types.is_datetime64_any_dtype(gdf_shp[col]):
                    gdf_shp[col] = gdf_shp[col].astype(str)
            gdf_shp.to_file(points_path, driver="ESRI Shapefile")
            if not gdf_lines.empty:
                gdf_lines_shp = gdf_lines.copy()
                for col in ("start_time_utc", "end_time_utc"):
                    if col in gdf_lines_shp.columns:
                        gdf_lines_shp[col] = gdf_lines_shp[col].astype(str)
                gdf_lines_shp.to_file(line_path, driver="ESRI Shapefile")
            written["points_shp"] = points_path
            written["line_shp"] = line_path

        return written, gdf_lines

    def summarize(self, gdf, timezone=DEFAULT_TIMEZONE):
        """Build a plain dict answering: what is this, and when did it happen.

        `first_contact_utc`/`last_contact_utc` are always present -- UTC is
        the one zone that's never ambiguous. `first_contact_local`/
        `last_contact_local` only appear when `gdf` has a `point_time_local`
        column (i.e. process_flight_data was called with a timezone), and
        never replace the UTC fields.
        """
        if gdf.empty:
            return {}

        first = gdf.iloc[0]
        last = gdf.iloc[-1]
        duration = last["point_time_utc"] - first["point_time_utc"]

        def fmt(ts):
            return ts.strftime("%Y-%m-%d %H:%M:%S %Z") if pd.notna(ts) else None

        summary = {
            "icao": first.get("icao"),
            "registration": first.get("registration"),
            "aircraft_type": first.get("model"),
            "description": first.get("desc"),
            "owner_op": first.get("owner_op"),
            "call_signs": sorted(gdf["call_sign"].dropna().unique().tolist()) if "call_sign" in gdf else [],
            "num_legs": int(gdf["leg_id"].max()) if "leg_id" in gdf and not gdf.empty else 0,
            "num_points": len(gdf),
            "first_contact_utc": fmt(first["point_time_utc"]),
            "last_contact_utc": fmt(last["point_time_utc"]),
            "timezone": timezone,
            "duration_minutes": round(duration.total_seconds() / 60, 1),
            "max_altitude_ft": float(gdf["altitude"].max()) if "altitude" in gdf and gdf["altitude"].notna().any() else None,
            "max_ground_speed_kt": float(gdf["ground_speed"].max()) if "ground_speed" in gdf and gdf["ground_speed"].notna().any() else None,
            "has_multilaterated_positions": bool(
                gdf["position_source"].astype(str).str.contains("mlat", case=False, na=False).any()
            ) if "position_source" in gdf else False,
        }

        if "point_time_local" in gdf.columns:
            summary["first_contact_local"] = fmt(first["point_time_local"])
            summary["last_contact_local"] = fmt(last["point_time_local"])

        return summary

    def headline_for(self, summary):
        """A one-line, plain-English answer to 'what happened and when'.

        UTC is always shown. If a local zone was requested, it leads, with
        UTC given right alongside it on its own line -- never the other way
        around, so a glance always finds the zone-proof time too.
        """
        if not summary:
            return "No trace data found."

        label = summary.get("registration") or summary.get("icao", "").upper()
        aircraft = summary.get("description") or summary.get("aircraft_type") or ""
        parts = [f"{label}"]
        if aircraft:
            parts.append(f"({aircraft}, hex {summary.get('icao')})")
        line1 = " ".join(parts)

        utc_start, utc_end = summary.get("first_contact_utc"), summary.get("last_contact_utc")
        if not utc_start or not utc_end:
            return f"{line1}\nNo timed positions found."

        duration = summary.get("duration_minutes")
        legs = summary.get("num_legs")
        leg_word = f"{legs} leg{'s' if legs != 1 else ''}"

        local_start, local_end = summary.get("first_contact_local"), summary.get("last_contact_local")
        if local_start and local_end:
            line2 = f"Tracked {local_start} \u2192 {local_end} ({duration:g} min, {leg_word})"
            line3 = f"UTC: {utc_start} \u2192 {utc_end}"
            return f"{line1}\n{line2}\n{line3}"

        line2 = f"Tracked {utc_start} \u2192 {utc_end} ({duration:g} min, {leg_word})"
        return f"{line1}\n{line2}"

    # ------------------------------------------------------------------
    # S3
    # ------------------------------------------------------------------

    def upload_directory_to_s3(self, local_dir, bucket_name, prefix=""):
        """Upload every file in a local directory to s3://bucket/prefix/."""
        if not self.s3_client:
            print("S3 client not configured; skipping upload.")
            return []

        uploaded = []
        for root, _dirs, files in os.walk(local_dir):
            for filename in files:
                local_path = os.path.join(root, filename)
                rel_path = os.path.relpath(local_path, local_dir)
                key = "/".join(filter(None, [prefix.strip("/"), rel_path]))
                self.s3_client.upload_file(local_path, bucket_name, key)
                uploaded.append(f"s3://{bucket_name}/{key}")
                print(f"Uploaded s3://{bucket_name}/{key}")
        return uploaded

    def upload_to_s3(self, gdf, bucket_name, csv_object_name, geojson_object_name):
        """Upload a GeoDataFrame as CSV and GeoJSON directly to S3 (legacy helper)."""
        if not self.s3_client:
            print("S3 client not configured; skipping upload.")
            return

        csv_buffer = BytesIO()
        gdf.drop(columns="geometry", errors="ignore").to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        self.s3_client.put_object(Bucket=bucket_name, Key=csv_object_name, Body=csv_buffer.getvalue())
        print(f"CSV uploaded to s3://{bucket_name}/{csv_object_name}")

        gdf_json = gdf.copy()
        for col in gdf_json.columns:
            if pd.api.types.is_datetime64_any_dtype(gdf_json[col]):
                gdf_json[col] = gdf_json[col].astype(str)

        self.s3_client.put_object(
            Bucket=bucket_name, Key=geojson_object_name, Body=gdf_json.to_json().encode("utf-8")
        )
        print(f"GeoJSON uploaded to s3://{bucket_name}/{geojson_object_name}")
