# flight_tracer/viz.py
"""Publication-ready map and chart rendering for flight traces.

Basemap and typography follow the CNN Visuals house style. Carto withdrew
anonymous tile access some time ago, so its providers are mapped onto Esri
equivalents rather than left to fail silently.
"""

import contextily as ctx
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import math
import os
from pathlib import Path
from urllib.parse import quote
import numpy as np
from xyzservices import TileProvider
import pandas as pd
import geopandas as gpd
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from shapely.ops import transform

from .geometry import route_geometry

DEFAULT_GAP_MINUTES = 5


def _coverage_segments(points, gap_minutes):
    """Classify connections by elapsed time, never connecting separate legs."""
    if not math.isfinite(gap_minutes) or gap_minutes <= 0:
        raise ValueError("gap_minutes must be a positive, finite number")
    points = points.to_crs(4326).copy()
    points["point_time_utc"] = pd.to_datetime(points["point_time_utc"], utc=True)
    keys = [key for key in ("icao", "leg_id") if key in points]
    if "leg_id" not in keys and "flight_leg" in points:
        keys.append("flight_leg")
    groups = points.groupby(keys, dropna=False) if keys else [(None, points)]
    rows = []
    for _, group in groups:
        ordered = group.sort_values("point_time_utc")
        records = list(ordered.itertuples())
        for previous, current in zip(records, records[1:]):
            elapsed = (current.point_time_utc - previous.point_time_utc).total_seconds()
            rows.append({
                "flight_leg": getattr(current, "flight_leg", None),
                "coverage_gap": not math.isfinite(elapsed) or elapsed > gap_minutes * 60,
                "geometry": route_geometry([previous.geometry, current.geometry]),
            })
    return gpd.GeoDataFrame(rows, columns=["flight_leg", "coverage_gap", "geometry"], crs=4326)


def _draw_coverage(ax, routes, colors, multi_leg):
    """Draw each observed connection or gap with its own line style."""
    segments, segment_colors, styles = [], [], []
    for row in routes.itertuples():
        geometry = row.geometry
        parts = geometry.geoms if geometry.geom_type == "MultiLineString" else [geometry]
        for part in parts:
            if part.geom_type != "LineString":
                continue
            segments.append(list(part.coords))
            segment_colors.append(colors.get(row.flight_leg, COLOR_FLIGHT) if multi_leg else COLOR_FLIGHT)
            styles.append((0, (4, 3)) if row.coverage_gap else "solid")
    ax.add_collection(LineCollection(segments, colors=segment_colors, linestyles=styles,
                                     linewidths=2.2, capstyle="round", zorder=3))

# Web Mercator repeats horizontally every circumference of the Earth.
WORLD_WIDTH = 2 * math.pi * 6378137


def _project_map_data(points, lines):
    """Use the shortest longitude window, shared by all routes and markers."""
    projected = points.to_crs(epsg=3857)
    routes = lines.to_crs(epsg=3857) if lines is not None and not lines.empty else None
    xs = np.sort(projected.geometry.x.unique())
    if len(xs) > 1:
        gaps = np.diff(np.append(xs, xs[0] + WORLD_WIDTH))
        gap_index = int(np.argmax(gaps))
        if gap_index != len(xs) - 1:
            left = xs[gap_index + 1]

            def wrap(x, y, z=None):
                x = np.asarray(x)
                return np.where(x < left - 1e-6, x + WORLD_WIDTH, x), y

            projected.geometry = projected.geometry.apply(lambda geom: transform(wrap, geom))
            if routes is not None:
                routes.geometry = routes.geometry.apply(lambda geom: transform(wrap, geom))
    return projected, routes


def _draw_basemap(ax, provider, zoom=None):
    """Fetch each visible world strip in tile coordinates, then shift it back."""
    west, east = ax.get_xlim()
    south, north = ax.get_ylim()
    half = WORLD_WIDTH / 2
    if -half <= west < east <= half:
        # Render the provider's full credit once in our wrapped footer.
        kwargs = {"source": provider, "reset_extent": True, "attribution": False}
        if zoom is not None:
            kwargs["zoom"] = zoom
        ctx.add_basemap(ax, **kwargs)
        return

    # Use one zoom for both halves so their tile detail matches at the seam.
    if zoom is None:
        zoom = max(0, math.ceil(math.log2(2 * WORLD_WIDTH / (east - west))))
        zoom = max(provider.get("min_zoom", 0), min(zoom, provider.get("max_zoom", 19)))
    images = []
    for world in range(math.floor((west + half) / WORLD_WIDTH),
                       math.ceil((east + half) / WORLD_WIDTH)):
        shift = world * WORLD_WIDTH
        w, e = max(west - shift, -half), min(east - shift, half)
        s, n = max(south, -half), min(north, half)
        if w >= e or s >= n:
            continue
        raster, extent = ctx.bounds2img(w, s, e, n, zoom=zoom, source=provider)
        images.append((raster, (extent[0] + shift, extent[1] + shift, extent[2], extent[3])))
    for raster, extent in images:
        ax.imshow(raster, extent=extent, interpolation="bilinear", zorder=0)
    ax.set_xlim(west, east)
    ax.set_ylim(south, north)

COLOR_TEXT = "#262626"
COLOR_MUTED = "#8e8e8e"
COLOR_AXIS = "#A6A6A6"
COLOR_GRID = "#ececec"
COLOR_BACKGROUND = "#FEFEFE"

# One color for the flight itself, wherever it shows up: the map route, and
# the altitude/speed chart lines. One flight, one color.
COLOR_FLIGHT = "#5194C3"

# First/last contact deliberately avoid red+green (reads as a holiday pair,
# and it's the one combination red-green colorblind readers can't tell
# apart). First contact is muted -- it's context. Last contact is the point
# that usually matters most in a breaking-news read, so it gets the bolder
# color; shape (circle vs. square) carries the rest of the distinction.
COLOR_FIRST_CONTACT = "#262626"
COLOR_LAST_CONTACT = "#F18851"

CATEGORY_COLORS = ["#5194C3", "#F8C153", "#C52622", "#53A796", "#F18851", "#7C4EA5"]

FONT_STACK = ["CNN Sans Display", "Helvetica Neue", "Arial", "DejaVu Sans"]

# AP style abbreviates all months except March through July.
AP_MONTHS = {
    1: "Jan.", 2: "Feb.", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "Aug.", 9: "Sept.", 10: "Oct.", 11: "Nov.", 12: "Dec.",
}


def _ap_date(ts):
    return f"{AP_MONTHS[ts.month]} {ts.day}, {ts.year}"


ASPECT_SIZES = {"16:9": (9.6, 5.4), "9:16": (5.4, 9.6)}


def _figure_size(figsize, aspect_ratio):
    if aspect_ratio not in ASPECT_SIZES:
        raise ValueError("aspect_ratio must be '16:9' or '9:16'")
    return figsize if figsize is not None else ASPECT_SIZES[aspect_ratio]


def _human_span(start, end):
    if start.date() == end.date():
        dates = _ap_date(start)
    elif (start.year, start.month) == (end.year, end.month):
        dates = f"{AP_MONTHS[start.month]} {start.day}–{end.day}, {start.year}"
    elif start.year == end.year:
        dates = f"{AP_MONTHS[start.month]} {start.day}–{AP_MONTHS[end.month]} {end.day}, {end.year}"
    else:
        dates = f"{_ap_date(start)}–{_ap_date(end)}"

    def clock(ts):
        return f"{ts.hour % 12 or 12}:{ts.minute:02d}"

    def period(ts):
        return "a.m." if ts.hour < 12 else "p.m."

    first, last = clock(start), clock(end)
    zone_start, zone_end = start.strftime("%Z") or "UTC", end.strftime("%Z") or "UTC"
    if zone_start != zone_end:
        times = f"{first} {period(start)} {zone_start}–{last} {period(end)} {zone_end}"
    elif start.date() == end.date() and period(start) == period(end):
        times = f"{first}–{last} {period(end)} {zone_end}"
    else:
        times = f"{first} {period(start)}–{last} {period(end)} {zone_end}"
    return f"{dates} · {times}"


def format_time_span(df, time_col=None):
    """Readable minute-precision dates; local spans retain their UTC companion."""
    time_col = time_col or ("point_time_local" if "point_time_local" in df else "point_time_utc")
    times = df[time_col].dropna().sort_values()
    if times.empty:
        return ""
    label = _human_span(times.iloc[0], times.iloc[-1])
    if time_col == "point_time_local" and "point_time_utc" in df:
        utc = df["point_time_utc"].dropna().sort_values()
        if not utc.empty:
            label += "\n" + _human_span(utc.iloc[0], utc.iloc[-1])
    return label


def _wrap_text(fig, text, width, fontsize, weight="normal"):
    """Wrap using actual font metrics, rather than a guessed character count."""
    from matplotlib.font_manager import FontProperties
    renderer = fig.canvas.get_renderer()
    font = FontProperties(family=FONT_STACK, size=fontsize, weight=weight)
    max_width = width * fig.bbox.width
    lines = []
    for paragraph in str(text).splitlines():
        line = ""
        for word in paragraph.split():
            candidate = f"{line} {word}".strip()
            if line and renderer.get_text_width_height_descent(candidate, font, False)[0] > max_width:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
    return "\n".join(lines)


def _header(fig, title, subtitle):
    """Lay out text and return the top of the available plotting panel."""
    y = 0.96
    for text, size, weight, color in ((title, 15, "bold", COLOR_TEXT),
                                      (subtitle, 10, "normal", COLOR_TEXT)):
        if not text:
            continue
        artist = fig.text(0.025, y, _wrap_text(fig, text, 0.95, size, weight),
                          fontsize=size, fontweight=weight, color=color, va="top")
        bounds = artist.get_window_extent(fig.canvas.get_renderer())
        y -= bounds.height / fig.bbox.height + 0.10 / fig.get_figheight()
    return y - 0.06 / fig.get_figheight()


def _footer(fig, text):
    artist = fig.text(0.025, 0.02, _wrap_text(fig, text, 0.95, 8), fontsize=8,
                      color=COLOR_MUTED, va="bottom")
    height = artist.get_window_extent(fig.canvas.get_renderer()).height / fig.bbox.height
    return artist, 0.02 + height + 0.12 / fig.get_figheight()

BASEMAPS = {
    "osm": ("OpenStreetMap.Mapnik", "OpenStreetMap contributors"),
    "esri-light": ("Esri.WorldGrayCanvas", "Esri"),
    "esri-street": ("Esri.WorldStreetMap", "Esri"),
    "esri-topo": ("Esri.WorldTopoMap", "Esri"),
    "esri-satellite": ("Esri.WorldImagery", "Esri"),
    "esri-natgeo": ("Esri.NatGeoWorldMap", "Esri"),
}

# Carto withdrew anonymous basemap access; its tiles now return watermarked
# "API key required" placeholders instead of a real basemap. Route the old
# names to an Esri equivalent so a call written years ago still draws a map.
RETIRED_BASEMAPS = {
    "carto": "esri-light",
    "carto-light": "esri-light",
    "cartodb": "esri-light",
    "cartodb.positron": "esri-light",
    "positron": "esri-light",
}

DEFAULT_BASEMAP = "esri-light"
MAPBOX_STYLES = {
    "mapbox": "streets-v12",
    "mapbox-streets": "streets-v12",
    "mapbox-light": "light-v11",
    "mapbox-dark": "dark-v11",
    "mapbox-outdoors": "outdoors-v12",
}
MAPBOX_CREDIT = "© Mapbox, © OpenStreetMap"


def configure_style():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": FONT_STACK,
        "text.color": COLOR_TEXT,
        "figure.facecolor": COLOR_BACKGROUND,
        "axes.facecolor": COLOR_BACKGROUND,
        "savefig.facecolor": COLOR_BACKGROUND,
        "xtick.color": COLOR_AXIS,
        "ytick.color": COLOR_AXIS,
        "grid.color": COLOR_GRID,
        "grid.linewidth": 1,
        "axes.edgecolor": COLOR_GRID,
        "axes.linewidth": 0.5,
    })


configure_style()


def resolve_basemap(background):
    """Return (provider, credit) for a basemap key, falling back to the default."""
    key = (background or DEFAULT_BASEMAP).lower()
    key = RETIRED_BASEMAPS.get(key, key)

    if key.startswith("mapbox"):
        if key not in MAPBOX_STYLES:
            raise ValueError("Unknown Mapbox background. Choose mapbox, mapbox-streets, "
                             "mapbox-light, mapbox-dark or mapbox-outdoors. "
                             "Mapbox Standard is not supported by the Static Tiles API.")
        token = os.environ.get("MAPBOX_ACCESS_TOKEN", "").strip()
        if not token:
            raise ValueError("Mapbox requires MAPBOX_ACCESS_TOKEN. Set this environment "
                             "variable to your Mapbox public access token.")
        provider = TileProvider(
            name=key,
            url="https://api.mapbox.com/styles/v1/mapbox/{style}/tiles/512/{z}/{x}/{y}@2x"
                "?access_token={access_token}",
            style=MAPBOX_STYLES[key], access_token=quote(token, safe=""),
            attribution=MAPBOX_CREDIT, min_zoom=0, max_zoom=22,
        )
        return provider, MAPBOX_CREDIT

    if key not in BASEMAPS:
        print(f"Unknown basemap '{background}'; using '{DEFAULT_BASEMAP}'.")
        key = DEFAULT_BASEMAP

    path, credit = BASEMAPS[key]
    provider = ctx.providers
    for part in path.split("."):
        provider = getattr(provider, part)
    return provider, provider.get("attribution") or credit


def _map_source_text(source, credit):
    return "\n".join(text for text in (
        f"Source: {source}" if source else "",
        f"Basemap: {credit}" if credit else "",
    ) if text)


def _add_mapbox_logo(fig, bottom):
    """Official black logo on the white footer; 40 px high at export DPI."""
    logo = plt.imread(Path(__file__).parent / "assets" / "mapbox-logo.png")
    height = 0.2
    width = height * logo.shape[1] / logo.shape[0]
    ax = fig.add_axes([0.025 + 0.2 / fig.get_figwidth(),
                       bottom + 0.2 / fig.get_figheight(),
                       width / fig.get_figwidth(), height / fig.get_figheight()])
    ax.imshow(logo)
    ax.set_axis_off()


def _add_basemap(ax, background, zoom=None):
    """Draw the basemap, retrying with the default provider if the first fails."""
    provider, credit = resolve_basemap(background)
    try:
        _draw_basemap(ax, provider, zoom)
        return credit
    except Exception as exc:
        if provider.name in MAPBOX_STYLES:
            # HTTP exceptions often contain the complete URL and access token.
            print(f"Could not load Mapbox tiles. Check your token, its URL restrictions, "
                  f"and account access; falling back to '{DEFAULT_BASEMAP}'.")
        else:
            print(f"Could not load the {credit} basemap ({exc}); falling back to '{DEFAULT_BASEMAP}'.")
        fallback_provider, fallback_credit = resolve_basemap(DEFAULT_BASEMAP)
        try:
            _draw_basemap(ax, fallback_provider, zoom)
            return fallback_credit
        except Exception as exc2:
            print(f"Fallback basemap failed too ({exc2}); drawing the route with no basemap.")
            return None


def plot_map(gdf_points, gdf_lines, headline, dek, source, output_path,
             background=DEFAULT_BASEMAP, figsize=None, pad_factor=0.25, zoom=None,
             leg_labels=None, gap_minutes=DEFAULT_GAP_MINUTES, aspect_ratio="16:9"):
    """Plot a flight trace: route, contact markers, basemap and CNN-style chrome.

    `source` is the flight-data attribution only (e.g. "ADS-B Exchange"),
    not a full sentence. The provider's complete attribution is added in a
    separate wrapped footer beneath the map, without an overlay on the tiles.

    `leg_labels`: optional {flight_leg: label} dict, for a multi-leg overview
    (e.g. "VOC4062 -- Sep 20, 13:00 UTC"). When given, the legend identifies
    each leg by that label instead of the single-flight first/last-contact
    markers -- with several distinct flights on one map, one global
    start/end pair says less than which line is which flight. Each leg gets
    a small dot at its own start instead, colored to match its line.

    Connections separated by more than `gap_minutes` are dashed to mark
    missing coverage, not an observed path. This does not split flight legs.
    """
    if gdf_points.crs is None:
        gdf_points = gdf_points.set_crs(epsg=4326)
    has_times = "point_time_utc" in gdf_points
    if has_times:
        gdf_lines = _coverage_segments(gdf_points, gap_minutes)
    points_3857, lines_3857 = _project_map_data(gdf_points, gdf_lines)
    has_gaps = has_times and lines_3857 is not None and lines_3857["coverage_gap"].any()

    figsize = _figure_size(figsize, aspect_ratio)
    fig = plt.figure(figsize=figsize)

    # Reserve fixed panels for the headline/dek and the source line, in figure
    # fractions. The rest is the map. Setting the axes' position explicitly
    # (rather than plt.subplots + tight_layout) means we know exactly how many
    # inches the map panel gets, so the geographic extent can be pre-padded to
    # that panel's aspect ratio below.
    top = _header(fig, headline, dek)
    _, expected_credit = resolve_basemap(background)
    _, fallback_credit = resolve_basemap(DEFAULT_BASEMAP)
    # Reserve enough space for either provider before fitting the map.
    candidates = [_map_source_text(source, credit) for credit in (expected_credit, fallback_credit)]
    reserved = max(candidates, key=lambda text: len(_wrap_text(fig, text, 0.95, 8).splitlines()))
    footer, bottom = _footer(fig, reserved)
    logo_bottom = bottom
    if expected_credit == MAPBOX_CREDIT:
        bottom += 0.6 / fig.get_figheight()
    left, right = 0.025, 0.975
    ax = fig.add_axes([left, bottom, right - left, top - bottom])

    legs = points_3857["flight_leg"].unique() if "flight_leg" in points_3857.columns else [None]
    multi_leg = len(legs) > 1
    colors = {leg: CATEGORY_COLORS[i % len(CATEGORY_COLORS)] for i, leg in enumerate(legs)}

    if lines_3857 is not None and has_times:
        _draw_coverage(ax, lines_3857, colors, multi_leg)
    elif lines_3857 is not None:
        for _, row in lines_3857.iterrows():
            color = colors.get(row.get("flight_leg"), COLOR_FLIGHT) if multi_leg else COLOR_FLIGHT
            gpd_series = lines_3857[lines_3857["flight_leg"] == row["flight_leg"]] if multi_leg else lines_3857
            gpd_series.plot(ax=ax, linewidth=2.2, color=color, zorder=3)
    else:
        points_3857.plot(ax=ax, marker="o", markersize=6, color=COLOR_FLIGHT, zorder=3)

    if leg_labels:
        # Multi-leg overview: legend by flight (a color swatch per leg),
        # not by first/last contact -- which flight is which matters more
        # here than where the whole tracked window happened to start or end.
        sort_col = "point_time_utc" if "point_time_utc" in points_3857.columns else points_3857.columns[0]
        for leg, group in points_3857.groupby("flight_leg"):
            leg_start = group.sort_values(sort_col).iloc[0]
            color = colors.get(leg, COLOR_FLIGHT)
            ax.scatter([leg_start.geometry.x], [leg_start.geometry.y], s=40, color=color,
                       edgecolor="white", linewidth=1, zorder=5, label=leg_labels.get(leg, leg))
        legend_fontsize = 8
    else:
        # First/last contact -- not "start/end": what's plotted is where
        # ADS-B picked up and lost the signal, which in a crash can sit well
        # short of where the aircraft actually came down.
        start = points_3857.iloc[0]
        end = points_3857.iloc[-1]
        ax.scatter([start.geometry.x], [start.geometry.y], s=60, color=COLOR_FIRST_CONTACT,
                   edgecolor="white", linewidth=1.2, zorder=5, label="First contact")
        ax.scatter([end.geometry.x], [end.geometry.y], s=70, color=COLOR_LAST_CONTACT,
                   edgecolor="white", linewidth=1.2, zorder=5, marker="s", label="Last contact")
        legend_fontsize = 9

    xmin, ymin, xmax, ymax = points_3857.total_bounds
    x_pad = max((xmax - xmin) * pad_factor, 500)
    y_pad = max((ymax - ymin) * pad_factor, 500)
    data_w = (xmax - xmin) + 2 * x_pad
    data_h = (ymax - ymin) + 2 * y_pad

    # geopandas' .plot() forces an equal-aspect axes (correctly -- geographic
    # data shouldn't stretch). Left alone, matplotlib satisfies that by
    # shrinking whichever side of the axes box doesn't match the data's
    # aspect ratio, which then throws off the saved image's actual
    # dimensions once combined with a tight bbox. Padding the extent to the
    # panel's own aspect ratio first means equal-aspect has nothing to
    # shrink, so the map fills the whole panel and the output stays the
    # requested landscape shape.
    panel_aspect = (figsize[0] * (right - left)) / (figsize[1] * (top - bottom))
    data_aspect = data_w / data_h
    if data_aspect > panel_aspect:
        target_h = data_w / panel_aspect
        y_pad += (target_h - data_h) / 2
    else:
        target_w = data_h * panel_aspect
        x_pad += (target_w - data_w) / 2

    ax.set_xlim(xmin - x_pad, xmax + x_pad)
    ax.set_ylim(ymin - y_pad, ymax + y_pad)
    ax.set_aspect("equal", adjustable="box")

    credit = _add_basemap(ax, background, zoom=zoom)
    if credit == MAPBOX_CREDIT:
        _add_mapbox_logo(fig, logo_bottom)
    # Tile bounds must never replace the extent fitted to this exact panel.
    ax.set_xlim(xmin - x_pad, xmax + x_pad)
    ax.set_ylim(ymin - y_pad, ymax + y_pad)

    ax.set_axis_off()
    handles, labels = ax.get_legend_handles_labels()
    if has_gaps:
        handles.append(Line2D([], [], color=COLOR_MUTED, linewidth=2.2, linestyle=(0, (4, 3))))
        labels.append("Tracking gap (approximate connection)")
    labels = [_wrap_text(fig, label, (right - left) * 0.80, legend_fontsize) for label in labels]
    ax.legend(handles, labels, loc="lower right", fontsize=legend_fontsize,
              frameon=True, facecolor="white", framealpha=0.85)

    footer.set_text(_wrap_text(fig, _map_source_text(source, credit), 0.95, 8))

    _save(fig, output_path, tight=False)


def plot_series(df, value_col, title, ylabel, output_path, source="",
                 time_col=None, color=COLOR_FLIGHT, figsize=None, aspect_ratio="16:9"):
    """A single-series time chart (altitude, speed) in the house style.

    Plots in `point_time_local` when the DataFrame has it (i.e. a timezone
    was requested upstream), otherwise UTC -- never a silent default to any
    one city's clock. Either way the subtitle names the zone actually on the
    axis and, when that zone is local, restates the same start/end in UTC
    right next to it, so the chart is never ambiguous on its own.
    """
    if time_col is None:
        time_col = "point_time_local" if "point_time_local" in df.columns else "point_time_utc"

    series = df[[time_col, value_col]].dropna().sort_values(time_col)
    if series.empty:
        print(f"No data to plot for {value_col}; skipping {output_path}.")
        return

    fig, ax = plt.subplots(figsize=_figure_size(figsize, aspect_ratio))
    ax.plot(series[time_col], series[value_col], color=color, linewidth=1.6)

    last = series.iloc[-1]
    ax.scatter([last[time_col]], [last[value_col]], s=28, color=color, zorder=5,
               edgecolor="white", linewidth=1)
    ax.annotate(f"{last[value_col]:,.0f}", (last[time_col], last[value_col]),
                textcoords="offset points", xytext=(6, 4), fontsize=11,
                fontweight="bold", color=COLOR_TEXT)

    # The x-axis is bare HH:MM, which says nothing about the date or zone on
    # its own. Every chart gets a subtitle naming both, and the tick format
    # grows a date if the trace spans more than one calendar day in that zone
    # (e.g. crosses local midnight).
    first_ts, last_ts = series[time_col].iloc[0], series[time_col].iloc[-1]
    spans_multiple_days = first_ts.date() != last_ts.date()
    if spans_multiple_days:
        tick_format = "%b %-d, %H:%M"
    else:
        tick_format = "%H:%M"
    top = _header(fig, title, format_time_span(df.dropna(subset=[time_col, value_col]), time_col))
    _, bottom = _footer(fig, source)

    ax.set_ylabel(ylabel, fontsize=10, color=COLOR_AXIS)
    ax.grid(axis="y", color=COLOR_GRID, linewidth=1)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(COLOR_GRID)
    # matplotlib's DateFormatter renders in UTC unless told otherwise -- a
    # tz-aware pandas column isn't enough on its own. Without `tz=` here, the
    # ticks would silently show UTC clock time even while the subtitle above
    # claims a local zone.
    ax.xaxis.set_major_formatter(mdates.DateFormatter(tick_format, tz=first_ts.tzinfo))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=4 if aspect_ratio == "9:16" else 7))
    ax.tick_params(axis="both", length=0, labelsize=9, colors=COLOR_AXIS)

    plt.tight_layout(rect=[0.015, bottom, 0.96, top])
    _save(fig, output_path, tight=False)


def _save(fig, output_path, tight=True):
    import os
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight" if tight else None)
    plt.close(fig)
    print(f"Saved {output_path}")
