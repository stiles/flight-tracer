# Backlog

Prioritize reliability and finding the right flight before adding more visual options. These are proposed features, not release commitments; commands below describe possible interfaces, not current options.

## Next

- [x] **Time-window selection.** Implemented locally: `--after` / `--before`, explicit timezone handling, inclusive bounds and separate output folders. See the [January 26 case study](docs/examples/a9a1ad-2020-01-26.md).
- [x] **Re-render saved data.** Implemented locally: `flight-tracer render FOLDER` redraws images from `trace.csv` with a new basemap, aspect ratio, gap threshold or timezone. Saved titles and labels carry over unless replaced.
- [x] **Handle archives without leg markers more clearly.** Implemented locally: warnings and optional `--infer-legs` based on explicit ground reports. Results are labeled as estimates; airborne gaps do not become flight boundaries.
- [x] **Data-quality summary.** Implemented locally: `data_quality` in `summary.json` and printed notes covering coverage gaps, stale and multilaterated positions, missing metadata and leg-boundary provenance. A quality note on the map itself is not done.
- [x] **Visual regression tests.** Implemented locally: `tests/test_visual.py` compares five renders (round-trip map with a gap and label, 9:16 map, multi-leg overview, altitude, 9:16 speed) with `tests/baseline_images/`, using a synthetic basemap so it runs offline. Regenerate with `FLIGHT_TRACER_UPDATE_BASELINES=1`. Renders match between matplotlib 3.9 and 3.10 and between macOS and Linux CI, now that figures always use the Agg canvas.
- [x] **Endpoint marker legibility.** Implemented locally: larger markers with a heavier white ring, and a merged "Start and last location" marker when the two would overlap at the map's scale.

Callsign lookup by date needs a source investigation next. Checked items are implemented in the working tree; consult the changelog for release status.

## Soon

- [x] **Editable titles and annotations.** Implemented locally: `--title`, `--dek` and `--label LAT,LON,TEXT` on `trace` and `render`, saved in `annotations.json`. Airport-code lookup (e.g. `--airport KLAX`) could build on this later.
- [x] **Saved output presets.** Implemented locally: named tables in `~/.config/flight-tracer/presets.toml`, picked with `--preset NAME` over a `[default]` table; `flight-tracer presets` lists them.
- [ ] **Data-quality note on the map.** Finish the remaining piece of the data-quality summary: a one-line footer such as "3 coverage gaps, longest 12 min," so readers see it without opening `summary.json`.
- [ ] **Glyph coverage.** Inter and the rest of the font stack lack CJK and many symbols, so `--title`, `--dek` or `--label` text in those scripts renders as empty boxes. At minimum, warn when a character has no glyph; consider a Noto fallback.

## Later

- [ ] **Chart framing changes** Improve the title display and styling to include more practical information about an aircraft, such as owner, and de-emphasize the aircraft type. Don't display UTC when `--timezone` is used. A more narrative flight and subhead would be useful, if possible. 
- [ ] **Improve docs with visual examples** Create more practical examples of flight maps, and speed/altitude charts, showing different styles for base layers, legs, colors, etc. Examples from [Medium article](https://medium.com/data-science-collective/what-the-heck-is-that-helicopter-doing-use-flighttracer-to-find-out-b964588e0467) could be a start. 
- [ ] **More flight track options** Allow user to change color and weight of flight path when exporting. Consider map extent, flight path and base layer where possible (satellite, for example, might need a different color than Mapbox monotone). Add a thin white casing under the route so it doesn't run through basemap place names; raster labels such as "Los Angeles" can't be moved. 
- [ ] **Aircraft metadata enrichment.** Improve sparse historical summaries while distinguishing historical information from current registry records.
- [ ] **Callsign lookup by date.** Accept identifiers such as `FDX9756`. First investigate historical lookup sources, availability and access requirements; aircraft assignments can vary by date.
- [ ] **OpenFreeMap support.** Explore a vector-map renderer alongside the current raster tiles, including styles such as Positron, Bright, Liberty, Dark and Fiord. Verify available styles during implementation.
- [ ] **Interactive HTML export.** Hover for timestamps, altitude and speed; inspect gaps and switch legs.


## Ongoing maintenance

- [ ] Verify multi-aircraft behavior, including leg selection, summaries and output grouping.
- [ ] Exercise provider failures and confirm clear errors, appropriate fallbacks and correct attribution.
- [ ] Maintain representative historical fixtures covering older record formats, missing leg flags, missing metadata and Date Line crossings.
- [ ] Check installation and upgrades, optional dependencies and CLI entry points in supported Python environments.
- [ ] Refresh the Python support range: add 3.14 to the CI matrix and classifiers, and consider dropping 3.9 (end of life October 2025).
- [ ] Clear deprecation warnings before they become errors: Click's `isolated_filesystem` in `tests/test_coverage.py` (removed in Click 9) and the NumPy scalar-conversion warning raised through pyproj's transformer.
- [ ] Script docs image regeneration so every embedded image rebuilds with one command. Record the README hero's exact command (`--icao a1f0d8 --date 2026-10-03 --leg 4 --background mapbox-light --timezone America/Los_Angeles`; the nearby examples use a different aircraft, `a40442`), and pin the image URL to a commit SHA as the README comment intends — it currently points at `main`.

See the [README](README.md) for currently supported features and the [changelog](CHANGELOG.md) for shipped changes.
