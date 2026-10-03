# Backlog

Prioritize reliability and finding the right flight before adding more visual options. These are proposed features, not release commitments; commands below describe possible interfaces, not current options.

## Next

- [x] **Time-window selection.** Implemented locally: `--after` / `--before`, explicit timezone handling, inclusive bounds and separate output folders. See the [January 26 case study](docs/examples/a9a1ad-2020-01-26.md).
- [x] **Re-render saved data.** Implemented locally: `flight-tracer render FOLDER` redraws images from `trace.csv` with a new basemap, aspect ratio, gap threshold or timezone. Labels and titles wait on editable annotations.
- [x] **Handle archives without leg markers more clearly.** Implemented locally: warnings and optional `--infer-legs` based on explicit ground reports. Results are labeled as estimates; airborne gaps do not become flight boundaries.
- [ ] **Data-quality summary.** Report coverage gaps, missing metadata, stale positions and whether leg boundaries were supplied or inferred.

The data-quality summary is the next priority. Checked items are implemented in the working tree; consult the changelog for release status.

## Soon

- [ ] **Callsign lookup by date.** Accept identifiers such as `FDX9756`. First investigate historical lookup sources, availability and access requirements; aircraft assignments can vary by date.
- [ ] **OpenFreeMap support.** Explore a vector-map renderer alongside the current raster tiles, including styles such as Positron, Bright, Liberty, Dark and Fiord. Verify available styles during implementation.
- [ ] **Editable titles and annotations.** Supply a headline, label airports and mark relevant locations without editing Python.
- [ ] **Saved output presets.** Reuse preferred aspect ratios, timezones, basemaps and output directories.

## Later

- [ ] **Interactive HTML export.** Hover for timestamps, altitude and speed; inspect gaps and switch legs.
- [ ] **Aircraft metadata enrichment.** Improve sparse historical summaries while distinguishing historical information from current registry records.

## Ongoing maintenance

- [ ] Verify multi-aircraft behavior, including leg selection, summaries and output grouping.
- [ ] Exercise provider failures and confirm clear errors, appropriate fallbacks and correct attribution.
- [ ] Maintain representative historical fixtures covering older record formats, missing leg flags, missing metadata and Date Line crossings.
- [ ] Check installation and upgrades, optional dependencies and CLI entry points in supported Python environments.

See the [README](README.md) for currently supported features and the [changelog](CHANGELOG.md) for shipped changes.
