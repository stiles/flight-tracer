import json
import os
from datetime import datetime

import click

from flight_tracer.core import FlightTracer
from flight_tracer.identify import parse_adsbx_url, resolve_n_number, resolve_timezone
from flight_tracer.viz import plot_map, plot_series


@click.group()
def cli():
    """FlightTracer: turn an N-number, ICAO hex or ADS-B Exchange URL into a
    mapped, summarized flight trace in one command."""
    pass


def _resolve_targets(icao, n_number, url):
    """Turn --icao/--n-number/--url into a list of (icao, note) and an optional date hint."""
    targets = []
    date_hint = None

    for value in icao:
        targets.append((value.strip().lower(), None))

    for value in n_number:
        info = resolve_n_number(value)
        note = f"{info['n_number']}"
        if info.get("owner_name"):
            note += f" / {info['owner_name']}"
        targets.append((info["icao"], note))
        click.echo(f"Resolved {value} -> icao={info['icao']} ({info.get('maker', '')} {info.get('model', '')})")

    if url:
        info = parse_adsbx_url(url)
        targets.append((info["icao"], "from URL"))
        if info.get("date"):
            date_hint = info["date"]
            click.echo(f"Parsed URL -> icao={info['icao']}, date={info['date']}")
        else:
            click.echo(f"Parsed URL -> icao={info['icao']} (no replay date, treating as recent)")

    if not targets:
        raise click.UsageError("Provide at least one of --icao, --n-number or --url.")

    return targets, date_hint


@click.command()
@click.option("--icao", multiple=True, help="ICAO hex code of the aircraft. Repeatable.")
@click.option("--n-number", multiple=True, help="FAA tail number (e.g. N358TV). Resolved via hangarbay. Repeatable.")
@click.option("--url", default=None, help="A globe.adsbexchange.com URL to parse for the ICAO hex and replay date.")
@click.option("--start", type=click.DateTime(formats=["%Y-%m-%d"]), help="Start date (YYYY-MM-DD).")
@click.option("--end", type=click.DateTime(formats=["%Y-%m-%d"]), help="End date (YYYY-MM-DD).")
@click.option("--date", type=click.DateTime(formats=["%Y-%m-%d"]), help="Shorthand for --start/--end on the same day.")
@click.option("--recent", is_flag=True, help="Force the recent-trace endpoint even if a date was found or given.")
@click.option("--timezone", default=None,
              help="IANA zone to add alongside UTC (e.g. America/Los_Angeles), or 'auto' to infer it "
                   "from the trace's first position. Default: UTC only.")
@click.option("--output", default="data", show_default=True, help="Directory to write the run's output folder into.")
@click.option("--filter-ground/--keep-ground", default=True, help="Drop points where altitude == 'ground'.")
@click.option("--background", default="esri-light", show_default=True,
              help="Basemap: osm, esri-light, esri-street, esri-topo, esri-satellite, esri-natgeo.")
@click.option("--formats", default="csv,geojson", show_default=True, help="Comma list of output formats: csv,geojson,shp.")
@click.option("--no-plots", is_flag=True, help="Skip map and chart rendering; write data only.")
@click.option("--bucket", default=None, help="If set, upload the output folder to this S3 bucket.")
@click.option("--aws-profile", default=None, help="AWS profile to use for --bucket uploads.")
def trace(icao, n_number, url, start, end, date, recent, timezone, output,
          filter_ground, background, formats, no_plots, bucket, aws_profile):
    """Fetch, process, map and summarize a flight trace in one step.

    Pick the entry point that matches what you have:

        flight-tracer trace --n-number N358TV
        flight-tracer trace --icao a40442
        flight-tracer trace --url "https://globe.adsbexchange.com/?replay=...&icao=a40442"

    With no date given, defaults to ADS-B Exchange's recent-trace endpoint
    (roughly the last few hours to a few days) -- the breaking-news case.
    Pass --start/--end (or --date) for a flight that happened further back.
    """
    targets, date_hint = _resolve_targets(icao, n_number, url)
    icaos = [t[0] for t in targets]

    if date:
        start_date, end_date = date.date(), date.date()
    elif start or end:
        start_date = (start or end).date()
        end_date = (end or start).date()
    elif date_hint and not recent:
        start_date, end_date = date_hint, date_hint
    else:
        start_date, end_date = None, None

    use_recent = recent or start_date is None

    tracer = FlightTracer(aircraft_ids=icaos)
    raw_df = tracer.get_traces(start_date, end_date, recent=use_recent)

    if raw_df.empty:
        click.echo("No trace data found. If this is an older flight, try --start/--end for the date it happened.")
        return

    if timezone and timezone.lower() == "auto":
        first_point = raw_df.dropna(subset=["lat", "lon"]).iloc[0]
        resolved_timezone = resolve_timezone("auto", lat=first_point["lat"], lon=first_point["lon"])
        click.echo(f"Inferred timezone from location: {resolved_timezone}")
    else:
        resolved_timezone = resolve_timezone(timezone)

    gdf = tracer.process_flight_data(raw_df, filter_ground=filter_ground, timezone=resolved_timezone)
    if gdf.empty:
        click.echo("No airborne points after filtering. Try --keep-ground if this aircraft never left the ground.")
        return

    icao_str = "_".join(sorted(set(icaos)))
    if use_recent:
        slug = f"{icao_str}_recent_{datetime.now().strftime('%Y%m%d')}"
    else:
        slug = f"{icao_str}_{start_date}_{end_date}"
    output_dir = os.path.join(output, slug)

    written, gdf_lines = tracer.write_outputs(gdf, output_dir, formats=tuple(formats.split(",")))

    summary = tracer.summarize(gdf, timezone=resolved_timezone)
    summary_path = os.path.join(output_dir, "summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    written["summary"] = summary_path

    click.echo("")
    click.echo(tracer.headline_for(summary))
    click.echo("")

    if not no_plots:
        label = summary.get("registration") or summary.get("icao", "").upper()
        aircraft = summary.get("description") or summary.get("aircraft_type") or ""
        headline = f"{label} \u2014 {aircraft}" if aircraft else label
        if summary.get("first_contact_local"):
            dek = (f"Tracked {summary['first_contact_local']} to {summary['last_contact_local']} "
                   f"(UTC: {summary['first_contact_utc']} to {summary['last_contact_utc']})")
        else:
            dek = f"Tracked {summary.get('first_contact_utc')} to {summary.get('last_contact_utc')}"
        multilaterated_note = " \u2014 some positions are multilaterated estimates" if summary.get("has_multilaterated_positions") else ""
        # plot_map credits the basemap tiles on its own, so it gets the bare
        # data-source label; the charts have no basemap, so they get a
        # complete "Source:" line.
        flight_source_label = f"ADS-B Exchange{multilaterated_note}"
        chart_source = f"Source: ADS-B Exchange{multilaterated_note}"

        map_path = os.path.join(output_dir, "map.png")
        plot_map(gdf, gdf_lines, headline, dek, flight_source_label, map_path, background=background)
        written["map"] = map_path

        alt_path = os.path.join(output_dir, "altitude.png")
        plot_series(gdf, "altitude", "Altitude", "Feet", alt_path, source=chart_source)
        written["altitude_chart"] = alt_path

        speed_path = os.path.join(output_dir, "speed.png")
        plot_series(gdf, "ground_speed", "Ground speed", "Knots", speed_path, source=chart_source)
        written["speed_chart"] = speed_path

    click.echo(f"\nWrote {len(written)} files to {output_dir}/")

    if bucket:
        tracer_up = FlightTracer(aircraft_ids=icaos, aws_profile=aws_profile)
        tracer_up.upload_directory_to_s3(output_dir, bucket, prefix=f"flight_tracer/{slug}")


@click.command()
@click.option("--n-number", required=True, help="FAA tail number, e.g. N358TV or 358TV.")
def resolve(n_number):
    """Look up an N-number's ICAO hex via the FAA registry, without fetching a trace."""
    try:
        info = resolve_n_number(n_number)
    except (ImportError, ValueError) as exc:
        raise click.ClickException(str(exc))

    click.echo(f"ICAO hex:  {info['icao']}")
    click.echo(f"N-number:  {info['n_number']}")
    click.echo(f"Aircraft:  {info.get('maker', '')} {info.get('model', '')}".strip())
    click.echo(f"Owner:     {info.get('owner_name', '')}")


cli.add_command(trace)
cli.add_command(resolve)

if __name__ == "__main__":
    cli()
