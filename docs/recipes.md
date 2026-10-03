# Recipes

[Back to README](../README.md) · [CLI reference](cli.md) · [Map styling](maps.md)

## Recent activity

```bash
flight-tracer trace --icao a40442
flight-tracer trace --n-number N358TV --leg latest
```

Tail numbers require `pip install "flight-tracer[faa]"`. Recent coverage varies; use a historical date if the flight is no longer in the recent endpoint.

## Historical URLs

Both replay and trace-view links supply a date:

```bash
flight-tracer trace --url "https://globe.adsbexchange.com/?replay=2026-09-16-01:58&icao=a40442"
flight-tracer trace --url "https://globe.adsbexchange.com/?icao=a9a1ad&showTrace=2020-01-26"
```

The replay time does not trim the trace to that minute, and URL latitude, longitude and zoom do not lock the output map's view. The date chooses the archive file; the map fits the returned route. A URL without either date parameter fetches recent activity.

To override the link's date:

```bash
flight-tracer trace --url "https://globe.adsbexchange.com/?icao=a40442&showTrace=2026-09-16" \
  --date 2026-09-17
```

## An older archive: January 26, 2020

```bash
flight-tracer trace --icao a9a1ad --date 2020-01-26 \
  --timezone America/Los_Angeles
```

This file uses seven-field records and includes earlier activity. It has no leg-boundary flags, so `--leg latest` does **not** isolate the final departure. Use `--after` / `--before` to select a time window, or opt into `--infer-legs --leg latest`. The [detailed case study](examples/a9a1ad-2020-01-26.md) covers both commands, evidence and limitations.

Archive dates refer to UTC files, not local calendar days. Files may also contain earlier trace points. Always inspect the returned times.

## Pick one leg or all legs

```bash
flight-tracer trace --icao abed10 --start 2026-09-26 --end 2026-09-27 --leg 1
flight-tracer trace --icao abed10 --start 2026-09-26 --end 2026-09-27 --leg all
```

Leg numbers come from the fetched trace. When several legs exist, omit `--leg` in an interactive terminal to see the table and choose. A callsign can label a detected leg, but is not a supported lookup input.

## Local time, automatically

```bash
pip install "flight-tracer[tz]"
flight-tracer trace --icao a40442 --date 2026-09-16 --timezone auto
```

The timezone is inferred from the first available position and used for the whole trace. It does not switch zones along an international route. Use an explicit zone when you need a particular newsroom or destination clock:

```bash
flight-tracer trace --icao abed10 --date 2026-09-27 --timezone Asia/Tokyo
```

## Include ground reports and export shapefiles

```bash
flight-tracer trace --icao a40442 --date 2026-09-16 \
  --keep-ground --formats csv,geojson,shp --output exports
```

By default, points whose altitude is reported as `ground` are removed. `--keep-ground` retains them; it does not recover missing positions. Shapefile field names may be shortened by the format's limits.

## Keep separate visual variants

```bash
flight-tracer trace --icao a40442 --date 2026-09-16 \
  --aspect-ratio 16:9 --background esri-light --output exports/landscape
flight-tracer trace --icao a40442 --date 2026-09-16 \
  --aspect-ratio 9:16 --background esri-topo --output exports/portrait
```

## Non-ICAO addresses

Preserve the `~` in an address from ADS-B Exchange:

```bash
flight-tracer trace --url "https://globe.adsbexchange.com/?icao=~29962a&showTrace=2026-09-23"
```

These traces can lack aircraft identity and other metadata. Do not infer an operator or mission from the address prefix or route pattern alone.

## Upload a run to S3

```bash
flight-tracer trace --icao a40442 --date 2026-09-16 \
  --bucket YOUR_BUCKET --aws-profile YOUR_PROFILE
```

This writes locally, then uploads the output folder using your configured AWS credentials.

## Troubleshooting

| Symptom | Try |
|---|---|
| No recent trace data | Add `--date YYYY-MM-DD` for the flight's UTC date. |
| No airborne points | Add `--keep-ground` to inspect ground reports. |
| `14 columns passed, passed data had 7 columns` | Update FlightTracer; the parser now supports older archives. For a local checkout, install with `pip install --no-deps -e .`. |
| `--leg latest` still shows several flights | The archive may lack leg flags; use `--after` / `--before` or try `--infer-legs`. |
| OSM access-blocked tiles | Update FlightTracer. It now identifies and caches OSM requests and rejects recognizable blocked tiles, falling back to Esri Light. |
| Missing Mapbox token | Set `MAPBOX_ACCESS_TOKEN`, choose a keyless basemap, or use `--no-plots`. |
| `--version` is not recognized | Update the installed package and check that your shell uses the intended Python environment. |
| Only a callsign such as `FDX9756` is available | Find the aircraft identity for that date first; callsign lookup is not implemented. |
