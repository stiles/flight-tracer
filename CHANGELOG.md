# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and versioning is [Semantic Versioning](https://semver.org/): patch for
bug fixes, minor for new features or changed output, major reserved for
declaring the API settled.

## [Unreleased]

## [0.2.1] - 2026-09-20

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
