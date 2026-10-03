# FlightTracer

Turn an aircraft tail number, ICAO hex, or [ADS-B Exchange](https://globe.adsbexchange.com/) link into a flight map, altitude and speed charts and reusable data.

```bash
pip install flight-tracer
flight-tracer trace --icao a40442
```

No date means recent activity. For a historical flight, add `--date YYYY-MM-DD`.

![Example flight map over Los Angeles, with start and last-location markers](https://raw.githubusercontent.com/stiles/flight-tracer/main/docs/images/flight-map.png)

*Example: An LAPD helicopter, N224LA, on Friday night patrol.*

## Start with what you have

| You have | Command |
|---|---|
| ICAO hex | `flight-tracer trace --icao a40442` |
| U.S. tail number | `flight-tracer trace --n-number N358TV` |
| Historical date | `flight-tracer trace --icao a40442 --date 2026-09-16` |
| ADS-B Exchange link | `flight-tracer trace --url "https://globe.adsbexchange.com/?icao=a9a1ad&showTrace=2020-01-26"` |
| Tail number to look up | `flight-tracer resolve --n-number N358TV` |

Tail-number lookup requires `pip install "flight-tracer[faa]"`. A callsign such as `FDX9756` cannot currently be used as an input; first find the aircraft's ICAO hex or tail number for that flight and date.

## Common recipes

### Fetch a date range and render every leg

```bash
flight-tracer trace --n-number N868FD \
  --start 2026-09-26 --end 2026-09-27 --leg all
```

Both dates are included. Each detected leg gets its own folder, plus an overview map. Use `--leg 1` for one leg or `--leg latest` for the most recent detected leg.

### Make a portrait map with local times

```bash
flight-tracer trace --icao a40442 --date 2026-09-16 \
  --aspect-ratio 9:16 --timezone America/Los_Angeles
```

Portrait outputs are 1080 × 1920. Local times appear alongside UTC; exported timestamps keep their full precision.

### Change the basemap and gap threshold

```bash
flight-tracer trace --icao a40442 --date 2026-09-16 \
  --background osm --gap-minutes 2
```

Connections across tracking gaps longer than two minutes are dashed. The default threshold is five minutes. The default basemap is `esri-light`; [see all map styles](https://github.com/stiles/flight-tracer/blob/main/docs/maps.md), including Mapbox with your own token.

### Export data without charts

```bash
flight-tracer trace --icao a40442 --date 2026-09-16 \
  --no-plots --formats csv,geojson --output exports
```

## What you get

A single-leg run writes:

```text
data/a40442_2026-09-16_2026-09-16/
├── map.png           # Route, start and last location, dates, attribution
├── altitude.png      # Altitude over time
├── speed.png         # Ground speed over time
├── trace.csv         # Recorded points and decoded fields
├── points.geojson    # Point geometries
├── line.geojson      # Routes by leg
└── summary.json      # Aircraft metadata, times and statistics
```

For several detected legs, the root contains the full data and `overview.png`; subfolders such as `leg1_FDX9756/` contain each leg's data and charts. Interactive runs ask which leg to use; `--leg all` skips the prompt. Non-interactive runs default to all legs.

Running the same aircraft/date selection again writes to the same folder. Use a different `--output` directory to keep variants.

## Installation and upgrades

Python 3.9 or newer is required. Optional extras add tail-number lookup and automatic timezone lookup:

```bash
pip install "flight-tracer[faa,tz]"
flight-tracer --version
flight-tracer trace --help
```

Quote extras such as `[faa,tz]` in zsh. To upgrade an existing installation:

```bash
pip install --upgrade flight-tracer
```

For local development, run this from the repository after installing dependencies:

```bash
pip install --no-deps -e .
```

## Understand the trace

- **Last location means last received position**, not a confirmed landing or crash site.
- **Dashed segments approximate missing coverage.** They do not establish the path flown. Exported route geometries include connections without dash styling.
- **Legs use the archive's boundary flags.** Older archives may lack them, so `--leg latest` cannot always isolate the final flight. Seven-field historical records are supported.
- **Date Line crossings are handled automatically.** Maps wrap around the Pacific where appropriate; exported routes split at ±180°.
- **Altitude and speed are raw, uncorrected values.** Missing metadata stays empty. Times default to UTC; local time is opt-in.

## More examples and reference

| Guide | What you'll find |
|---|---|
| [Recipes](https://github.com/stiles/flight-tracer/blob/main/docs/recipes.md) | Historical links, older archives, ground points, timezones and troubleshooting |
| [Map styling](https://github.com/stiles/flight-tracer/blob/main/docs/maps.md) | Aspect ratios, basemaps, Mapbox tokens, OSM caching and tracking gaps |
| [Python examples](https://github.com/stiles/flight-tracer/blob/main/docs/python.md) | Fetching, selecting time windows, plotting and working with fleets |
| [CLI reference](https://github.com/stiles/flight-tracer/blob/main/docs/cli.md) | Options, defaults and date precedence |
| [Changelog](https://github.com/stiles/flight-tracer/blob/main/CHANGELOG.md) | Release history |

## Contributing and releasing

Run checks with `python -m pytest tests/`. See [PUBLISH.md](https://github.com/stiles/flight-tracer/blob/main/PUBLISH.md) for the release workflow.

## Credits and license

Flight data comes from [ADS-B Exchange](https://globe.adsbexchange.com/). Consider [subscribing](https://store.adsbexchange.com/collections/subscriptions) or [contributing data](https://www.adsbexchange.com/ways-to-join-the-exchange/). FAA tail-number resolution uses [hangarbay](https://pypi.org/project/hangarbay/). Keep the basemap attribution in exported maps.

FlightTracer is released under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/legalcode).
