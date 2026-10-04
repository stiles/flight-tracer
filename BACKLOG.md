# Backlog

Prioritize reliability and finding the right flight before adding more visual options. These are proposed features, not release commitments; commands below describe possible interfaces, not current options.

## Next

- [x] **Time-window selection.** Implemented locally: `--after` / `--before`, explicit timezone handling, inclusive bounds and separate output folders. See the [January 26 case study](docs/examples/a9a1ad-2020-01-26.md).
- [x] **Re-render saved data.** Implemented locally: `flight-tracer render FOLDER` redraws images from `trace.csv` with a new basemap, aspect ratio, gap threshold or timezone. Saved titles and labels carry over unless replaced.
- [x] **Handle archives without leg markers more clearly.** Implemented locally: warnings and optional `--infer-legs` based on explicit ground reports. Results are labeled as estimates; airborne gaps do not become flight boundaries.
- [x] **Data-quality summary.** Implemented locally: `data_quality` in `summary.json` and printed notes covering coverage gaps, stale and multilaterated positions, missing metadata and leg-boundary provenance. A quality note on the map itself is not done.

Callsign lookup by date needs a source investigation next. Checked items are implemented in the working tree; consult the changelog for release status.

## Soon

- [x] **Editable titles and annotations.** Implemented locally: `--title`, `--dek` and `--label LAT,LON,TEXT` on `trace` and `render`, saved in `annotations.json`. Airport-code lookup (e.g. `--airport KLAX`) could build on this later.
- [x] **Saved output presets.** Implemented locally: named tables in `~/.config/flight-tracer/presets.toml`, picked with `--preset NAME` over a `[default]` table; `flight-tracer presets` lists them.

## Later

- [ ] **Aircraft metadata enrichment.** Improve sparse historical summaries while distinguishing historical information from current registry records.
- [ ] **Callsign lookup by date.** Accept identifiers such as `FDX9756`. First investigate historical lookup sources, availability and access requirements; aircraft assignments can vary by date.
- [ ] **OpenFreeMap support.** Explore a vector-map renderer alongside the current raster tiles, including styles such as Positron, Bright, Liberty, Dark and Fiord. Verify available styles during implementation.
- [ ] **Interactive HTML export.** Hover for timestamps, altitude and speed; inspect gaps and switch legs.


## Ongoing maintenance

- [ ] Verify multi-aircraft behavior, including leg selection, summaries and output grouping.
- [ ] Exercise provider failures and confirm clear errors, appropriate fallbacks and correct attribution.
- [ ] Maintain representative historical fixtures covering older record formats, missing leg flags, missing metadata and Date Line crossings.
- [ ] Check installation and upgrades, optional dependencies and CLI entry points in supported Python environments.

See the [README](README.md) for currently supported features and the [changelog](CHANGELOG.md) for shipped changes.
