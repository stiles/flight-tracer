# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and versioning is [Semantic Versioning](https://semver.org/): patch for
bug fixes, minor for new features or changed output, major reserved for
declaring the API settled.

## [Unreleased]

### Fixed

- `--url` and `parse_adsbx_url` now accept ADS-B Exchange's `~`-prefixed
  non-ICAO hexes (TIS-B / track-file IDs with no transponder identity
  behind them, e.g. `~29962a`), instead of raising "Could not find a
  6-character ICAO hex." The tilde is part of the hex ADS-B Exchange
  expects back on its trace URLs -- dropping it 404s -- so it's kept
  through fetching, not just parsing.

## [0.2.2] - 2026-09-20

### Added

- Multi-leg handling: `flight-tracer trace` now detects when an aircraft
  flew several distinct flights in the requested window (common for any
  busy commercial aircraft) and renders each leg separately -- one full
  single-flight map/chart/summary per leg, in its own subfolder, plus an
  `overview.png` legended by flight instead of cramming every leg into one
  confusing map and timeline chart.
- `--leg`: a leg number, `latest`, or `all` (the default) to control the
  above. Prompts interactively when omitted and more than one leg is
  found; defaults to `all` without prompting when not running in a
  terminal, so a script or cron job never hangs waiting for input.
- `FlightTracer.leg_table()`: per-leg callsign, UTC start/end, duration and
  point count, used to detect and describe a multi-leg trace before
  rendering it.

### Fixed

- `summarize()`'s `num_legs` used `leg_id.max()`, which misreports a trace
  already filtered down to one leg (e.g. leg 3 of 5) as "3 legs" instead
  of 1. Now counts distinct leg IDs present.
- Callsigns were forward-filled per aircraft globally rather than within
  each leg, so a leg whose callsign hadn't been broadcast yet in its first
  few messages inherited whatever the *previous* leg's callsign was --
  silently splitting one physical leg into two entries wherever something
  grouped by `flight_leg` (map legends, `create_linestrings`). Now filled
  within each `(icao, leg_id)` group, backfilling a leg's own later
  callsign into its leading points instead.
- `pip install flight-tracer[faa]`/`[tz]` fails on zsh (macOS's default
  shell) with "no matches found" -- square brackets are a glob pattern to
  zsh. Quoted every `pip install ...[extra]` in the README and, more
  importantly, in the `ImportError` messages users actually see and
  copy-paste when `hangarbay` or `timezonefinder` is missing.

## [0.2.1] - 2026-09-20

### Fixed

- `--timezone auto` printed a raw `AttributeError: _ARRAY_API not found`
  traceback on environments with a stale `scipy` (built against NumPy 1.x's
  ABI) installed alongside NumPy 2.x. `timezonefinder`'s `numba` dependency
  opportunistically tries to use whatever `scipy` happens to be present for
  BLAS acceleration, unrelated to `flight-tracer` itself; the crash was
  caught internally and `--timezone auto` still resolved correctly either
  way, which is exactly what made it look like noise instead of the real
  defect it was. Sets `NUMBA_DISABLE_JIT=1` before importing
  `timezonefinder` (only if the caller hasn't already set an opinion),
  which skips the BLAS-acceleration path entirely.

## [0.2.0] - 2026-09-20

A rebuild around one command instead of a fetch/process/export chain, driven
by real newsroom use.

### Added

- `flight-tracer trace`: fetch, decode legs, map, chart and summarize in one
  step, into one output folder. Picks its entry point from what you have:
  - `--n-number` (resolved to an ICAO hex via the FAA registry, `hangarbay`
    -- requires the `faa` extra)
  - `--icao`
  - `--url` (parses the ICAO hex and, if present, the replay date out of a
    globe.adsbexchange.com link)
- `flight-tracer resolve --n-number`: look up an ICAO hex without fetching a
  trace.
- `flight_tracer.identify`: `parse_adsbx_url()`, `resolve_n_number()`,
  `resolve_timezone()`.
- `flight_tracer.viz`: CNN-styled map and altitude/speed chart rendering,
  with a basemap fallback chain.
- `--timezone auto`: infer the local zone from the trace's first position
  via `timezonefinder` (requires the `tz` extra), for when you want local
  time but don't know the zone for wherever this happened.
- Tests for URL parsing, flag-driven leg detection, timezone resolution and
  a map-aspect-ratio regression.

### Changed

- Flight legs now come from ADS-B Exchange's own `flags & 2` marker (its
  landing/takeoff detector) instead of a configurable time-gap guess.
  Nothing to tune.
- Times default to UTC everywhere -- the zone ADS-B Exchange, ATC and pilots
  already use. Local time is opt-in via `--timezone`, and when requested,
  it's always paired with UTC rather than replacing it: the terminal
  headline, `summary.json`, the map dek and every chart subtitle restate
  the same span in both.
- Default basemap moved off the retired `CartoDB.Positron` (Carto withdrew
  anonymous tile access) to `esri-light`, with old Carto names mapped to an
  Esri equivalent automatically.
- Map route and both charts now share one color (`#5194C3`) instead of the
  map defaulting to orange while the charts used blue.
- First/last contact map markers moved off teal + red -- besides reading as
  a holiday pairing, it's the one hue combination red-green colorblind
  readers can't separate.
- Map source line now credits the flight data and the basemap tiles
  separately ("Sources: ADS-B Exchange (flight); Esri (basemap)") instead
  of crediting only one of the two.

### Fixed

- `plot_map()` could save a portrait PNG instead of the requested landscape
  `figsize`: geopandas' `.plot()` forces equal-aspect axes, and the map
  never pre-padded the extent to match the panel's shape first, so
  matplotlib's equal-aspect adjustment shrank the axes box and
  `bbox_inches="tight"` cropped to that shrunk box plus the header/footer
  text.
- Chart x-axes were silently rendering in UTC regardless of the requested
  timezone: matplotlib's `DateFormatter` renders in UTC by default even
  given a timezone-aware pandas column, unless `tz=` is passed explicitly.

### Removed

- The `fetch`/`process`/`export`/`upload`/`plot` CLI subcommands and the
  `export_flight_data()`/`plot_flights()` Python methods, replaced by
  `trace`/`resolve` and `write_outputs()`/`summarize()`/`headline_for()`.
- The checked-in `data/` sample outputs (pre-rewrite export format).
- `setup.cfg`, stale duplicate packaging metadata superseded by `setup.py`.

## [0.1.7] - 2025-02-09

Last release before the 0.2.0 rebuild. See git history for changes prior to
this changelog's introduction.
