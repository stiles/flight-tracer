# Python examples

[Back to README](../README.md) · [Recipes](recipes.md) · [Map styling](maps.md)

## Fetch, export and plot

```python
from datetime import date
from flight_tracer import FlightTracer
from flight_tracer.viz import format_time_span, plot_map, plot_series

tracer = FlightTracer(aircraft_ids=["a40442"])
raw = tracer.get_traces(date(2026, 9, 16), date(2026, 9, 16))
# For recent activity instead: raw = tracer.get_traces(recent=True)
if raw.empty:
    raise RuntimeError("No trace data returned")

zone = "America/Los_Angeles"
points = tracer.process_flight_data(raw, timezone=zone)
if points.empty:
    raise RuntimeError("No airborne points returned")

summary = tracer.summarize(points, timezone=zone)
print(tracer.headline_for(summary))
written, routes = tracer.write_outputs(points, "data/python-example")
plot_map(
    points, routes, "Aircraft a40442", format_time_span(points),
    "ADS-B Exchange", "data/python-example/map.png",
    background="esri-light", aspect_ratio="16:9", gap_minutes=5,
)
plot_series(
    points, "altitude", "Altitude", "Feet",
    "data/python-example/altitude.png", source="Source: ADS-B Exchange",
)
```

To mark locations, pass `labels=[{"lat": 33.9425, "lon": -118.408, "text": "LAX"}]` to `plot_map`. The extent widens to include them.

`write_outputs` writes the selected data formats (CSV and GeoJSON by default). Unlike the CLI, this method does not create charts or `summary.json`; call plotting functions or serialize the summary yourself.

## Select a time window from an older archive

This selects the final recorded departure in the January 26, 2020 `a9a1ad` archive. The cutoff is specific to this file, not a general leg-detection rule.

```python
from datetime import date
import pandas as pd
from flight_tracer import FlightTracer
from flight_tracer.viz import format_time_span, plot_map

tracer = FlightTracer(aircraft_ids=["a9a1ad"])
raw = tracer.get_traces(date(2020, 1, 26), date(2020, 1, 26))
if raw.empty:
    raise RuntimeError("No trace data returned")

start = pd.Timestamp("2020-01-26T17:06:35.843Z")
end = pd.Timestamp("2020-01-26T18:00:00Z")
selected = raw.loc[raw["point_time_utc"].between(start, end)].copy()
points = tracer.process_flight_data(selected, timezone="America/Los_Angeles")
if points.empty:
    raise RuntimeError("No airborne points in the selected interval")

written, routes = tracer.write_outputs(points, "data/a9a1ad-final-departure")
plot_map(
    points, routes, "A9A1AD", format_time_span(points), "ADS-B Exchange",
    "data/a9a1ad-final-departure/map.png",
)
```

The ground report at the cutoff is removed by the default ground filter, so the plotted airborne span begins around 9:06:57 a.m. PST. The endpoint is the last received position, not a verified crash location.

## Resolve identities and URLs

```python
from flight_tracer import resolve_n_number, parse_adsbx_url

identity = resolve_n_number("N358TV")  # Requires flight-tracer[faa]
print(identity["icao"])

link = parse_adsbx_url(
    "https://globe.adsbexchange.com/?icao=a9a1ad&showTrace=2020-01-26"
)
print(link["icao"], link["date"])
```

## Summarize a fleet

```python
from flight_tracer import FlightTracer

tracer = FlightTracer(aircraft_ids=["a40442", "ac308f", "ae4af6"])
raw = tracer.get_traces(recent=True)
if raw.empty:
    raise RuntimeError("No trace data returned")
points = tracer.process_flight_data(raw)
for icao, aircraft in points.groupby("icao"):
    print(tracer.headline_for(tracer.summarize(aircraft)))
    print(tracer.leg_table(aircraft))
```

## Upload existing output

```python
from flight_tracer import FlightTracer

tracer = FlightTracer(aircraft_ids=["a40442"], aws_profile="YOUR_PROFILE")
tracer.upload_directory_to_s3(
    "data/python-example", "YOUR_BUCKET", prefix="flight_tracer/example"
)
```
