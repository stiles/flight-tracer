"""Load a saved run folder back into a GeoDataFrame, so it can be re-rendered."""

import json
import os

import geopandas as gpd
import pandas as pd
import pytz

# Identifiers that look numeric must stay text (hex "123456", squawk "0123").
TEXT_COLUMNS = {col: str for col in
                ("icao", "registration", "model", "desc", "owner_op", "call_sign", "squawk",
                 "emergency", "flight_leg", "leg_detection", "position_source")}
BOOL_COLUMNS = ("is_stale", "altitude_is_geometric", "vertical_rate_is_geometric")


def read_json(path):
    try:
        with open(path) as handle:
            return json.load(handle)
    except FileNotFoundError:
        return {}


def load_saved_trace(folder, timezone=None):
    """Read `trace.csv` from a run folder; add `point_time_local` for `timezone`.

    Local times are recomputed from UTC rather than parsed, so a different
    zone can be applied without refetching. Returns a GeoDataFrame.
    """
    path = os.path.join(folder, "trace.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No trace.csv in {folder}. Re-rendering needs the CSV export "
            "(it is written by default; --formats must include csv)."
        )

    df = pd.read_csv(path, dtype=TEXT_COLUMNS)
    if df.empty:
        raise ValueError(f"{path} has no rows.")
    df["point_time_utc"] = pd.to_datetime(df["point_time_utc"], utc=True, format="ISO8601")
    df = df.drop(columns=["point_time_local"], errors="ignore")
    for col in BOOL_COLUMNS:
        if col in df:
            df[col] = df[col].astype(str).str.lower().eq("true")
    # Folders written before leg_detection was recorded.
    if "leg_detection" not in df:
        df["leg_detection"] = "unknown"
    if timezone:
        df["point_time_local"] = df["point_time_utc"].dt.tz_convert(pytz.timezone(timezone))

    return gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=4326,
    )
