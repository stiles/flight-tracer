# CLI reference

[Back to README](../README.md) · [Recipes](recipes.md)

Use the installed command for the options available in your version:

```bash
flight-tracer --version
flight-tracer --help
flight-tracer trace --help
flight-tracer resolve --help
```


```
flight-tracer trace
  --icao HEX              ICAO hex code. Repeatable.
  --n-number TAIL          FAA tail number, e.g. N358TV. Repeatable. Requires flight-tracer[faa].
  --url URL                A globe.adsbexchange.com URL to parse.
  --start / --end DATE     Historical date range (YYYY-MM-DD).
  --date DATE              Shorthand for --start/--end on the same day.
  --recent                 Force the recent-trace endpoint even if a date was found or given.
  --after TIMESTAMP       Inclusive start bound; full date and time required.
  --before TIMESTAMP      Inclusive end bound; full date and time required.
  --window-timezone ZONE  Zone for bounds without an offset. Default: UTC.
  --infer-legs             Infer ground-stop boundaries only for aircraft without leg flags.
  --leg CHOICE            A leg number, latest, or all. Prompts when interactive and omitted.
  --timezone ZONE          Add local times alongside UTC: an IANA zone (e.g. America/Chicago) or
                           'auto' to infer one from the trace's first position. Default: UTC only.
  --output DIR             Parent directory for the run's output folder. Default: data.
  --filter-ground          Drop ground points (default). --keep-ground to disable.
  --background NAME        Basemap. Default: esri-light.
  --formats LIST           Comma list: csv,geojson,shp. Default: csv,geojson.
  --no-plots               Skip map/chart rendering; write data only.
  --aspect-ratio RATIO     16:9 (default) or 9:16, for all maps and charts.
  --gap-minutes NUMBER     Dash map connections across gaps longer than this. Default: 5.
  --bucket NAME            Upload the output folder to this S3 bucket.
  --aws-profile NAME       AWS profile for --bucket uploads.

flight-tracer render FOLDER
  --background NAME        Basemap. Default: esri-light.
  --aspect-ratio RATIO     16:9 (default) or 9:16.
  --gap-minutes NUMBER     Dash map connections across gaps longer than this. Default: 5.
  --timezone ZONE          IANA zone, 'auto' or 'utc'. Default: the zone the run was saved with.
  --output DIR             Write images here instead of replacing the run's own.

flight-tracer resolve --n-number TAIL
  Print the ICAO hex, aircraft type and registered owner for a tail number.
```

Historical ranges include both dates. `--date` takes precedence over `--start`/`--end`, which take precedence over the URL date. `--recent` forces the recent endpoint. If only `--start` or `--end` is supplied, that date is used for both. Dates select UTC archive files; `--timezone` changes display times, not which files are fetched.

## Data quality

Each run prints notable findings after the headline and records all of them under `data_quality` in `summary.json`: `gap_count`, `longest_gap_minutes`, `gap_minutes_total` and `coverage_pct` (tracked time not inside a gap); `stale_positions` and `mlat_positions` counts and percentages; `missing_values` for altitude and ground speed; `missing_metadata`; and `leg_boundaries` per aircraft (`archive_flags`, `inferred_ground_stop` or `unmarked`).

Gaps follow the map's rule: consecutive points in the same aircraft and leg more than `--gap-minutes` apart. Time between legs is not a gap. Ground filtering can widen a gap, so treat coverage as a statement about the points kept, not about what the aircraft did. Metadata is reported missing only when no point has it.

## Re-rendering a saved run

`flight-tracer render FOLDER` redraws maps and charts from a run's `trace.csv` without fetching again. The run must have been saved with the `csv` format. Options you leave out use the defaults, not the original run's choices, except `--timezone`, which defaults to the zone in `summary.json`. Local times are recomputed from UTC.

Only images are written: `map.png`, `altitude.png` and `speed.png`, plus `overview.png` and per-leg subfolders when the CSV holds several legs. Data files are never rewritten, so `summary.json` keeps its original timezone. Without `--output`, existing images are replaced. A run that was narrowed to one leg re-renders as that leg. Folders saved before `leg_detection` was recorded render normally, with leg detection shown as unknown.

## Time windows

Explicit `Z` or numeric offsets take precedence over `--window-timezone`. Naive timestamps use that zone; ambiguous or nonexistent local times are rejected. Use an explicit offset to resolve a daylight-saving ambiguity. `--timezone` controls display only.

Without `--date`, `--start`/`--end`, a URL date or `--recent`, the window's UTC dates select the historical files. With only one bound, its UTC date is fetched; supply a date range to search a wider interval. Explicit archive dates still control fetching even when a window extends outside them.

Bounds are inclusive and apply after leg detection and ground filtering, before leg selection and output. Original leg IDs are preserved. Empty selections report an error. Windowed output folders include normalized UTC bounds; inferred runs add `_inferred`. `selection.json` records the choices. These suffixes avoid overwriting a full-day export, but rerunning the same selection still replaces its files.

## Optional leg inference

`--infer-legs` applies per aircraft only when no usable archive leg markers exist. It looks for consecutive explicit `ground` reports at least five minutes apart and within one kilometer, after an earlier airborne report. The later ground report starts the next inferred leg. Numeric altitude at or below zero and gaps between airborne reports never trigger this rule.

This is conservative: it can miss stops without explicit ground reports, and two reports do not establish continuous ground coverage. `leg_detection` in points, routes and summaries records `archive_flags`, `inferred_ground_stop` or `unmarked`. The CLI warns about unmarked traces and labels inferred results.
