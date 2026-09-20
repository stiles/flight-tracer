#!/usr/bin/env python
"""
fetch_from_json.py

The fleet scenario: a JSON file lists several aircraft (e.g. a police
department's helicopters), and you want traces for all of them in one run.
"""

import requests

from flight_tracer import FlightTracer
from flight_tracer.viz import plot_map

JSON_URL = "https://stilesdata.com/lapd-helicopters/lapd_aircraft.json"

print("Fetching aircraft list...")
response = requests.get(JSON_URL, timeout=30)
response.raise_for_status()
icao_codes = [aircraft["icao"] for aircraft in response.json()]
print(f"Extracted {len(icao_codes)} ICAO codes: {icao_codes}")

tracer = FlightTracer(aircraft_ids=icao_codes)

print("\nFetching recent trace data for the fleet...")
raw_df = tracer.get_traces(recent=True)

if raw_df.empty:
    print("No trace data was fetched.")
else:
    gdf = tracer.process_flight_data(raw_df, timezone="America/Los_Angeles")

    output_dir = "data/lapd_fleet"
    written, gdf_lines = tracer.write_outputs(gdf, output_dir)
    print(f"Wrote: {list(written.values())}")

    for icao in gdf["icao"].unique():
        aircraft_gdf = gdf[gdf["icao"] == icao]
        summary = tracer.summarize(aircraft_gdf)
        print("\n" + tracer.headline_for(summary))

    plot_map(
        gdf, gdf_lines,
        headline="LAPD air fleet",
        dek="Recent flight activity",
        source="Source: ADS-B Exchange",
        output_path=f"{output_dir}/map.png",
    )
