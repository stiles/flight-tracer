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

flight-tracer resolve --n-number TAIL
  Print the ICAO hex, aircraft type and registered owner for a tail number.
```

Historical ranges include both dates. `--date` takes precedence over `--start`/`--end`, which take precedence over the URL date. `--recent` forces the recent endpoint. If only `--start` or `--end` is supplied, that date is used for both. Dates select UTC archive files; `--timezone` changes display times, not which files are fetched.
