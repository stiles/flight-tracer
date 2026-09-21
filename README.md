# FlightTracer: tracking ADS-B Exchange flights

[![PyPI version](https://img.shields.io/pypi/v/flight-tracer.svg)](https://pypi.org/project/flight-tracer/)
[![License: CC0-1.0](https://licensebuttons.net/p/zero/1.0/88x31.png)](https://creativecommons.org/publicdomain/zero/1.0/)

FlightTracer turns whatever you have about an aircraft — an N-number, an ICAO hex, or a pasted [ADS-B Exchange](https://globe.adsbexchange.com/) URL — into a mapped, summarized flight trace in one command.

---

## Pick the right entry point

Start from what you have, not from a list of steps.

| You have | Run |
|---|---|
| An N-number from a reporter or scanner traffic | `flight-tracer trace --n-number N358TV` |
| An ICAO hex you spotted on the globe | `flight-tracer trace --icao a40442` |
| A URL someone sent you from globe.adsbexchange.com | `flight-tracer trace --url "https://globe.adsbexchange.com/?replay=2026-09-16-01:58&icao=a40442"` |
| Just the tail number, no ICAO handy | `flight-tracer resolve --n-number N358TV` (prints the hex without fetching anything) |

Each of those is the whole workflow: fetch, decode legs, map, chart, summarize. There's no separate `process` or `export` step, and no filename to remember — everything for one run lands in one folder.

## Installation

```bash
pip install flight-tracer
```

N-number lookups need the FAA registry client, [hangarbay](https://pypi.org/project/hangarbay/):

```bash
pip install "flight-tracer[faa]"
```

(the quotes matter on zsh, macOS's default shell -- without them, `[faa]` gets read as a glob pattern and zsh fails with "no matches found")

Without it, `--icao` and `--url` still work; `--n-number` raises a clear error telling you to install it.

---

## The newsroom scenarios this is built for

**A helicopter crash. You have an N-number.**

```bash
flight-tracer trace --n-number N358TV
```

This resolves the N-number to its ICAO hex via the FAA registry, then fetches ADS-B Exchange's *recent* trace — roughly the last few hours to a few days of coverage, no date required. That's the breaking-news default: you don't know the date yet, you just know it was recent.

**You can see an aircraft on the globe and have its ICAO hex.**

```bash
flight-tracer trace --icao a40442
```

Same recent-trace default. If it's not recent — the aircraft flew hours or days ago and dropped out of the short-lived recent trace — add a date:

```bash
flight-tracer trace --icao a40442 --date 2026-09-14
# or a range:
flight-tracer trace --icao a40442 --start 2026-09-10 --end 2026-09-14
```

**Someone sends you a globe.adsbexchange.com link.**

```bash
flight-tracer trace --url "https://globe.adsbexchange.com/?replay=2026-09-16-01:58&icao=a40442&lat=34.251&lon=-118.614&zoom=7.0"
```

The `icao` and `replay` date come straight out of the URL — nothing to retype. A live link with no `replay` param (just `?icao=...`) is treated as recent, same as the bare `--icao` case.

## What one run produces

```
data/a40442_2026-09-16_2026-09-16/
├── trace.csv        # every point: time (UTC + local), lat/lon, altitude, speed, leg
├── points.geojson
├── line.geojson      # one LineString per flight leg
├── map.png           # route over a basemap, start/end markers, headline + dek
├── altitude.png      # altitude over time
├── speed.png         # ground speed over time
└── summary.json      # the plain-English answer to "what is this, and when"
```

Every run also prints the headline straight to the terminal:

```
N358TV (AEROSPATIALE AS-350 Ecureuil, hex a40442)
Tracked 2026-09-16 00:23:28 UTC → 2026-09-16 01:55:25 UTC (91.9 min, 1 leg)
```

### Times are UTC unless you ask for local

ADS-B Exchange, ATC and pilots are all UTC-native, and a global newsroom has no reason to default to any one city's clock. So by default, everything — the terminal headline, `summary.json`, the CSV, the charts — stays in UTC, and there's no `point_time_local` column at all. One zone, nothing to get out of sync.

Ask for local time with `--timezone`, and it's added *alongside* UTC, never in place of it — every artifact that shows a local time restates the same span in UTC right next to it:

```bash
flight-tracer trace --icao a40442 --date 2026-09-16 --timezone America/New_York
# Tracked 2026-09-15 20:23:28 EDT → 2026-09-15 21:55:25 EDT (91.9 min, 1 leg)
# UTC: 2026-09-16 00:23:28 UTC → 2026-09-16 01:55:25 UTC
```

Don't know the local zone for wherever this happened? `--timezone auto` infers it from the trace's first position (via [timezonefinder](https://pypi.org/project/timezonefinder/), offline, no API):

```bash
flight-tracer trace --icao a40442 --date 2026-09-16 --timezone auto
# Inferred timezone from location: America/Los_Angeles
```

Requires the `tz` extra: `pip install "flight-tracer[tz]"` (quoted, for zsh).

### Flight legs, decoded rather than guessed

Earlier versions split legs by a configurable time-gap threshold. ADS-B Exchange already marks the start of each leg in its own data (`flags & 2` in the raw trace, its own landing/takeoff detector), so FlightTracer just reads that flag instead of guessing from a gap in timestamps. Nothing to tune.

### When one aircraft flew several flights

A busy commercial aircraft's "recent" trace is often several distinct flights, not one — an A320 doing a day of rotations, say. Cramming five takeoffs and landings into one map and one timeline chart reads as one confusing flight rather than five ordinary ones, so a multi-leg trace renders differently by default:

```
data/a6f3d3_recent_20260920/
├── trace.csv, points.geojson, line.geojson, summary.json   # the whole trace, every leg
├── overview.png       # all legs on one map, legended by flight (callsign + date)
├── leg1_VOC4070/       # each leg gets its own full single-flight render:
│   ├── map.png, altitude.png, speed.png, trace.csv, points.geojson, line.geojson, summary.json
├── leg2_VOC4071/
├── leg3_VOC4062/
├── leg4_VOC4062/
└── leg5_VOC4062/
```

Running interactively with more than one leg and no `--leg` prints the leg table and asks:

```
5 legs found -- this aircraft flew more than once in this window:
   1  VOC4070    Sep 20 00:13 → Sep 20 00:16 UTC  (3 min, 26 pts)
   2  VOC4071    Sep 20 01:26 → Sep 20 03:10 UTC  (104 min, 537 pts)
   3  VOC4062    Sep 20 12:59 → Sep 20 15:37 UTC  (159 min, 644 pts)
   4  VOC4062    Sep 20 17:01 → Sep 20 18:26 UTC  (84 min, 268 pts)
   5  VOC4062    Sep 20 20:20 → Sep 21 01:11 UTC  (292 min, 845 pts)
Which leg? (a number, 'latest', or 'all')
```

Pass `--leg` to skip the prompt: a number narrows *everything* (data and renders) to just that flight, same flat shape as a single-leg trace; `latest` picks the most recent leg; `all` (the default, including in a non-interactive run — a script or cron job is never left hanging on a prompt) renders every leg separately plus the overview.

```bash
flight-tracer trace --icao a6f3d3 --leg 3       # just the San José -> Mexico City flight
flight-tracer trace --icao a6f3d3 --leg latest  # whatever it's doing most recently
flight-tracer trace --icao a6f3d3 --leg all     # every leg, explicitly
```

### Basemaps

Default is `esri-light`, a quiet gray canvas that lets the route carry the map. Other options: `osm`, `esri-street`, `esri-topo`, `esri-satellite`, `esri-natgeo`. Carto withdrew anonymous tile access, so any old `carto`/`positron` reference is mapped onto `esri-light` automatically rather than silently failing.

```bash
flight-tracer trace --icao a40442 --background esri-satellite
```

---

## Full CLI options

```
flight-tracer trace
  --icao HEX              ICAO hex code. Repeatable.
  --n-number TAIL          FAA tail number, e.g. N358TV. Repeatable. Requires flight-tracer[faa].
  --url URL                A globe.adsbexchange.com URL to parse.
  --start / --end DATE     Historical date range (YYYY-MM-DD).
  --date DATE              Shorthand for --start/--end on the same day.
  --recent                 Force the recent-trace endpoint even if a date was found or given.
  --timezone ZONE          Add local times alongside UTC: an IANA zone (e.g. America/Chicago) or
                           'auto' to infer one from the trace's first position. Default: UTC only.
  --output DIR             Parent directory for the run's output folder. Default: data.
  --filter-ground          Drop ground points (default). --keep-ground to disable.
  --background NAME        Basemap. Default: esri-light.
  --formats LIST           Comma list: csv,geojson,shp. Default: csv,geojson.
  --no-plots               Skip map/chart rendering; write data only.
  --bucket NAME            Upload the output folder to this S3 bucket.
  --aws-profile NAME       AWS profile for --bucket uploads.

flight-tracer resolve --n-number TAIL
  Print the ICAO hex, aircraft type and registered owner for a tail number.
```

## Using FlightTracer in Python

```python
from flight_tracer import FlightTracer
from flight_tracer.viz import plot_map, plot_series

tracer = FlightTracer(aircraft_ids=["a40442"])
raw_df = tracer.get_traces(recent=True)                  # or (start_date, end_date)

gdf = tracer.process_flight_data(raw_df, timezone="America/Los_Angeles")
summary = tracer.summarize(gdf)
print(tracer.headline_for(summary))

written, gdf_lines = tracer.write_outputs(gdf, "data/a40442")
plot_map(gdf, gdf_lines, "N358TV", "Recent activity", "ADS-B Exchange",
          "data/a40442/map.png")
plot_series(gdf, "altitude", "Altitude", "Feet", "data/a40442/altitude.png")
```

### Resolving an N-number or a URL yourself

```python
from flight_tracer import resolve_n_number, parse_adsbx_url

info = resolve_n_number("N358TV")
# {'icao': 'a40442', 'n_number': 'N358TV', 'maker': 'EUROCOPTER', 'model': 'AS 350 B2', 'owner_name': '...'}

info = parse_adsbx_url("https://globe.adsbexchange.com/?replay=2026-09-16-01:58&icao=a40442")
# {'icao': 'a40442', 'date': date(2026, 9, 16), 'time': '01:58', 'lat': None, 'lon': None, 'zoom': None}
```

### Fleets: several aircraft in one call

```python
tracer = FlightTracer(aircraft_ids=["a40442", "ac308f", "ae4af6"])
# or from a hosted list:
tracer = FlightTracer(meta_url="https://stilesdata.com/lapd-helicopters/lapd_aircraft.json")

raw_df = tracer.get_traces(recent=True)
gdf = tracer.process_flight_data(raw_df)
for icao in gdf["icao"].unique():
    print(tracer.headline_for(tracer.summarize(gdf[gdf["icao"] == icao])))
```

### AWS S3

```python
tracer.upload_directory_to_s3("data/a40442_2026-09-16_2026-09-16", "my-bucket", prefix="flight_tracer")
```

Or from the CLI: `flight-tracer trace --icao a40442 --bucket my-bucket --aws-profile my-profile`.

---

## Notes on the data

- Values such as altitude and ground speed are raw and uncorrected.
- `has_multilaterated_positions` in the summary flags when part of a track came from multilateration rather than a direct ADS-B position — expect noisier speed readings in those stretches.
- ADS-B datetimes are UTC (Zulu); every output also carries the requested local zone, so nothing needs a manual conversion downstream.

---

## Roadmap

- Metadata enrichment beyond the FAA registry (e.g. ICAO aircraft-type lookups)
- Parallel fetching for large fleets
- Mapbox-backed basemaps for house-style GL maps
- Overflight/noise-style analysis helpers

---

## Releasing

See [PUBLISH.md](PUBLISH.md) and [CHANGELOG.md](CHANGELOG.md). In short: `./publish.sh`.

---

## Credits

Thanks to [ADS-B Exchange](https://globe.adsbexchange.com/) for providing open flight data. Consider [subscribing](https://store.adsbexchange.com/collections/subscriptions) or [contributing data](https://www.adsbexchange.com/ways-to-join-the-exchange/).

N-number resolution uses [hangarbay](https://pypi.org/project/hangarbay/), an FAA aircraft registry client.

## License

This project is licensed under the **Creative Commons CC0 1.0 Universal** Public Domain Dedication.

[![CC0 Badge](https://licensebuttons.net/p/zero/1.0/88x31.png)](https://creativecommons.org/publicdomain/zero/1.0/legalcode)
