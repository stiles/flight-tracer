# Map styling

[Back to README](../README.md) · [Recipes](recipes.md)

## Frame and labels


Maps and charts default to a **16:9 landscape frame (1920 × 1080)**.
Use `--aspect-ratio 9:16` for a **1080 × 1920 portrait frame**; it applies
to the overview, individual flight maps, and altitude/speed charts:

```bash
flight-tracer trace --icao a40442 --aspect-ratio 9:16
```

The map fills its available panel without stretching geography. Headings,
deks, and sources wrap to fit the frame. Dates read like
“Oct. 3, 2026 · 3:37–4:27 p.m. UTC”; local times retain a separate UTC line.
The exported data keeps full timestamp precision.

A borderless legend sits below the map, above the source credits. Small
black and orange circles mark **Start** and **Last location**. The last
received position is not assumed to be a landing. Overview flight keys and
tracking-gap explanations use the same footer area and wrap to fit.

In Python, both `plot_map` and `plot_series` accept `aspect_ratio="9:16"`.
An explicit `figsize` still overrides the preset for custom-sized output.

## Date Line crossings and missing coverage

Routes crossing the International Date Line stay together on the map, with
basemap tiles wrapped across the seam. Exported routes split at ±180° into
a MultiLineString so GIS tools do not draw a line across the world. These
splits do not change flight legs, timestamps, or recorded positions.

Missing tracking coverage is shown separately: map connections between
positions more than five minutes apart are dashed and labeled as approximate
connections in the legend. They do not show the aircraft's known path through
that interval. Use `--gap-minutes 2` to change the cutoff (or `gap_minutes=2`
in `plot_map`). This styling applies to overview and individual-leg maps;
it does not change flight legs or add observations to the exported data.
GeoJSON and shapefile routes contain unstyled connections between positions.

## Choose a basemap

| `--background` | Appearance | Key needed? |
|---|---|---|
| `esri-light` (default) | Gray canvas | No |
| `esri-street` | Streets | No |
| `esri-topo` | Topographic | No |
| `esri-satellite` | Satellite imagery | No |
| `esri-natgeo` | National Geographic | No |
| `osm` | OpenStreetMap streets | No |
| `mapbox` / `mapbox-streets` | Streets v12 | Yes |
| `mapbox-light` | Light v11 | Yes |
| `mapbox-dark` | Dark v11 | Yes |
| `mapbox-outdoors` | Outdoors v12 | Yes |

Legacy `carto`/`positron` names map to `esri-light`. OpenFreeMap is not currently implemented.

```bash
flight-tracer trace --icao a40442 --background esri-satellite
```

## OpenStreetMap

`--background osm` identifies tile requests as FlightTracer and caches tiles
across runs. It requests only tiles for the map being rendered, sequentially,
and stops on denied or throttled requests. Failed responses and recognizable
OSM access-blocked images are rejected before drawing; the map then falls
back to Esri Light with the correct credit.

The cache follows server expiry headers, using seven days when no expiry is
provided. Expired tiles are revalidated using ETag/Last-Modified when available.
The default cache is `~/.cache/flight-tracer/osm-v1` (or under
`XDG_CACHE_HOME`). Set `FLIGHT_TRACER_CACHE_DIR` to choose another location.
Old Contextily cache entries are not reused.

OSM's community service is best-effort and has a
[tile usage policy](https://operations.osmfoundation.org/policies/tiles/).
This option is for modest, user-requested maps, not bulk or scheduled tile
collection. Use another provider for high-volume output.

## Mapbox

Set a Mapbox public access token in your environment, then select a style:

```bash
export MAPBOX_ACCESS_TOKEN="YOUR_MAPBOX_PUBLIC_ACCESS_TOKEN"
flight-tracer trace --icao a40442 --background mapbox
flight-tracer trace --icao a40442 --background mapbox-light --aspect-ratio 9:16
```

`mapbox` and `mapbox-streets` use Streets v12. Other options are
`mapbox-light` (Light v11), `mapbox-dark` (Dark v11), and `mapbox-outdoors`
(Outdoors v12). The same names work with `plot_map(background=...)` in Python.
These use Mapbox's 512-pixel tiles at double resolution, with text attribution
included in the footer. Tokens are read at runtime and
Mapbox request errors do not print the token-bearing URLs.

Mapbox's newer **Standard** style is not available through its
[Static Tiles API](https://docs.mapbox.com/api/maps/static-tiles/).
Requests use your Mapbox account's tile quota and billing. A token restricted
to browser URLs may be rejected by this Python client. Missing tokens produce
an error before fetching flights; tile failures fall back to Esri Light and
credit that provider instead. `--no-plots` does not require a Mapbox token.

For publishing, retain the exported attribution and follow Mapbox's
[attribution guidance](https://docs.mapbox.com/help/dive-deeper/attribution/).

