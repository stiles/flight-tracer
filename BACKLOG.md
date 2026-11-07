# Backlog

Prioritize reliability and finding the right flight before adding more visual options. These are proposed features, not release commitments; commands below describe possible interfaces, not current options.

## Next

- [x] **Time-window selection.** Implemented locally: `--after` / `--before`, explicit timezone handling, inclusive bounds and separate output folders. See the [January 26 case study](docs/examples/a9a1ad-2020-01-26.md).
- [x] **Re-render saved data.** Implemented locally: `flight-tracer render FOLDER` redraws images from `trace.csv` with a new basemap, aspect ratio, gap threshold or timezone. Saved titles and labels carry over unless replaced.
- [x] **Handle archives without leg markers more clearly.** Implemented locally: warnings and optional `--infer-legs` based on explicit ground reports. Results are labeled as estimates; airborne gaps do not become flight boundaries.
- [x] **Data-quality summary.** Implemented locally: `data_quality` in `summary.json` and printed notes covering coverage gaps, stale and multilaterated positions, missing metadata and leg-boundary provenance. A quality note on the map itself is not done.
- [x] **Visual regression tests.** Implemented locally: `tests/test_visual.py` compares five renders (round-trip map with a gap and label, 9:16 map, multi-leg overview, altitude, 9:16 speed) with `tests/baseline_images/`, using a synthetic basemap so it runs offline. Regenerate with `FLIGHT_TRACER_UPDATE_BASELINES=1`. Renders match across macOS and Linux now that figures always use the Agg canvas, but only within one matplotlib minor release (3.11 changed text rendering), so baselines record their matplotlib version and a dedicated `visual` CI job pins it. Regenerate on 3.11 when local development moves past Python 3.10.
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
- [ ] **Authenticated ADS-B Exchange access.** Historical requests now return HTTP 403 ("Historical data requires a verified session"), so `trace --date` and `--url` fail for everyone. Find out whether ADS-B Exchange offers a documented, licensed route to historical traces (their paid API, for example), read its terms, and if so accept a key from an environment variable the way Mapbox tokens work. Don't imitate a browser session. Also check whether the `--recent` path is gated the same way.
- [ ] **Callsign lookup by date.** Accept identifiers such as `FDX9756`. First investigate historical lookup sources, availability and access requirements; aircraft assignments can vary by date.
- [ ] **OpenFreeMap support.** Explore a vector-map renderer alongside the current raster tiles, including styles such as Positron, Bright, Liberty, Dark and Fiord. Verify available styles during implementation.
- [ ] **Interactive HTML export.** Hover for timestamps, altitude and speed; inspect gaps and switch legs.


## Ongoing maintenance

- [ ] Verify multi-aircraft behavior, including leg selection, summaries and output grouping.
- [ ] Exercise provider failures and confirm clear errors, appropriate fallbacks and correct attribution.
- [ ] Maintain representative historical fixtures covering older record formats, missing leg flags, missing metadata and Date Line crossings.
- [ ] Check installation and upgrades, optional dependencies and CLI entry points in supported Python environments.
- [x] Refresh the Python support range. Implemented locally: 3.14 added to the CI matrix and classifiers, 3.9 dropped. 3.14 passes locally; CI hasn't run it yet.
- [x] Clear deprecation warnings. Implemented locally: Click's `isolated_filesystem`, `shapely.ops.transform` and the ragged-row DataFrame construction in `core.py`. The NumPy/pyproj warning no longer reproduces with current dependencies. Matplotlib 3.10.9 still emits its own NumPy timedelta warning.
- [x] Script docs image regeneration. Implemented locally: `scripts/docs_images.py` re-renders the README hero and `--pin` points its URL at the image's last commit. Blocked for now: ADS-B Exchange answers historical requests with HTTP 403, "Historical data requires a verified session," so no historical image can be rendered until the tool has a legitimate way to authenticate (see the ADS-B Exchange API access idea below). The hero command is recorded in the script.

See the [README](README.md) for currently supported features and the [changelog](CHANGELOG.md) for shipped changes.
