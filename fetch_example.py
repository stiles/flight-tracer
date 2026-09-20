#!/usr/bin/env python
"""
fetch_example.py

The newsroom scenario: you have an ICAO hex (or an N-number, or a pasted
ADS-B Exchange URL) and need a mapped, summarized trace fast. This mirrors
what `flight-tracer trace` does under the hood, using the Python API
directly so it's easy to adapt in a notebook.
"""

from flight_tracer import FlightTracer
from flight_tracer.viz import plot_map, plot_series

ICAO = "a40442"
START, END = None, None  # None, None = ADS-B Exchange's "recent" trace

tracer = FlightTracer(aircraft_ids=[ICAO])

print("Fetching raw flight trace data...")
raw_df = tracer.get_traces(START, END, recent=(START is None))

if raw_df.empty:
    print("No trace data was fetched. Try passing --start/--end for a known date.")
else:
    print("\nProcessing into a GeoDataFrame (legs come from ADS-B Exchange's own flag, not a guess)...")
    # Times stay UTC unless you ask for local -- pass timezone="America/Los_Angeles"
    # (or any IANA zone) to add a point_time_local column alongside point_time_utc.
    gdf = tracer.process_flight_data(raw_df)

    summary = tracer.summarize(gdf)
    print("\n" + tracer.headline_for(summary))

    output_dir = f"data/{ICAO}_example"
    written, gdf_lines = tracer.write_outputs(gdf, output_dir)
    print(f"\nWrote: {list(written.values())}")

    plot_map(
        gdf, gdf_lines,
        headline=f"{summary['registration']} \u2014 {summary['description']}",
        dek=f"Tracked {summary['first_contact_utc']} to {summary['last_contact_utc']}",
        source="ADS-B Exchange",  # plot_map credits the basemap on its own
        output_path=f"{output_dir}/map.png",
    )
    plot_series(gdf, "altitude", "Altitude", "Feet", f"{output_dir}/altitude.png")
    plot_series(gdf, "ground_speed", "Ground speed", "Knots", f"{output_dir}/speed.png")
