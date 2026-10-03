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
import numpy as np
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
                                     linewidths=2.2, zorder=3))

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
        kwargs = {"source": provider, "reset_extent": False}
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

    if key not in BASEMAPS:
        print(f"Unknown basemap '{background}'; using '{DEFAULT_BASEMAP}'.")
        key = DEFAULT_BASEMAP

    path, credit = BASEMAPS[key]
    provider = ctx.providers
    for part in path.split("."):
        provider = getattr(provider, part)
    return provider, credit


def _add_basemap(ax, background, zoom=None):
    """Draw the basemap, retrying with the default provider if the first fails."""
    provider, credit = resolve_basemap(background)
    try:
        _draw_basemap(ax, provider, zoom)
        return credit
    except Exception as exc:
        print(f"Could not load the {credit} basemap ({exc}); falling back to '{DEFAULT_BASEMAP}'.")
        fallback_provider, fallback_credit = resolve_basemap(DEFAULT_BASEMAP)
        try:
            _draw_basemap(ax, fallback_provider, zoom)
            return fallback_credit
        except Exception as exc2:
            print(f"Fallback basemap failed too ({exc2}); drawing the route with no basemap.")
            return None


def plot_map(gdf_points, gdf_lines, headline, dek, source, output_path,
             background=DEFAULT_BASEMAP, figsize=(10, 7.5), pad_factor=0.25, zoom=None,
             leg_labels=None, gap_minutes=DEFAULT_GAP_MINUTES):
    """Plot a flight trace: route, contact markers, basemap and CNN-style chrome.

    `source` is the flight-data attribution only (e.g. "ADS-B Exchange"),
    not a full sentence -- the basemap's own credit is added automatically,
    so the saved source line reads "Sources: ADS-B Exchange (flight); Esri
    (basemap)" rather than crediting only one of the two things on the map.

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

    fig = plt.figure(figsize=figsize)

    # Reserve fixed panels for the headline/dek and the source line, in figure
    # fractions. The rest is the map. Setting the axes' position explicitly
    # (rather than plt.subplots + tight_layout) means we know exactly how many
    # inches the map panel gets, so the geographic extent can be pre-padded to
    # that panel's aspect ratio below.
    top, bottom, left, right = 0.85, 0.06, 0.02, 0.98
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

    ax.set_axis_off()
    handles, labels = ax.get_legend_handles_labels()
    if has_gaps:
        handles.append(Line2D([], [], color=COLOR_MUTED, linewidth=2.2, linestyle=(0, (4, 3))))
        labels.append("Tracking gap (approximate connection)")
    ax.legend(handles, labels, loc="lower right", fontsize=legend_fontsize,
              frameon=True, facecolor="white", framealpha=0.85)

    fig.text(0.02, 0.97, headline, fontsize=15, fontweight="bold", color=COLOR_TEXT, va="top", wrap=True)
    if dek:
        fig.text(0.02, 0.915, dek, fontsize=11, color=COLOR_TEXT, va="top", wrap=True)

    # A map draws on two attributions -- the flight data and the basemap
    # tiles -- so credit both by name rather than bolting "Basemap: X" onto
    # a "Source:" line meant for one.
    attributions = []
    if source:
        attributions.append(f"{source} (flight)")
    if credit:
        attributions.append(f"{credit} (basemap)")

    if len(attributions) > 1:
        source_line = "Sources: " + "; ".join(attributions)
    elif attributions:
        source_line = f"Source: {attributions[0].split(' (')[0]}"
    else:
        source_line = ""

    fig.text(0.02, 0.02, source_line, fontsize=9, color=COLOR_MUTED, va="bottom")

    _save(fig, output_path, tight=False)


def plot_series(df, value_col, title, ylabel, output_path, source="",
                 time_col=None, color=COLOR_FLIGHT, figsize=(9, 3.6)):
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

    fig, ax = plt.subplots(figsize=figsize)
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
    tz_abbrev = first_ts.strftime("%Z") if first_ts.tzinfo else "UTC"
    spans_multiple_days = first_ts.date() != last_ts.date()
    if spans_multiple_days:
        date_label = f"{_ap_date(first_ts)} \u2013 {_ap_date(last_ts)}"
        tick_format = "%b %-d, %H:%M"
    else:
        date_label = _ap_date(first_ts)
        tick_format = "%H:%M"
    subtitle = f"{date_label} \u00b7 {tz_abbrev}"

    # If the axis is in a local zone, restate the same span in UTC so the
    # chart is never ambiguous on its own -- the whole point of defaulting to
    # UTC is defeated if a local-only chart escapes without it.
    if time_col == "point_time_local" and "point_time_utc" in df.columns:
        utc_start = df["point_time_utc"].iloc[0].strftime("%H:%M")
        utc_end = df["point_time_utc"].iloc[-1].strftime("%H:%M")
        subtitle += f" (UTC {utc_start}\u2013{utc_end})"

    fig.text(0.01, 0.97, title, fontsize=13, fontweight="bold", color=COLOR_TEXT, va="top")
    fig.text(0.01, 0.87, subtitle, fontsize=10, color=COLOR_MUTED, va="top")

    ax.set_ylabel(ylabel, fontsize=10, color=COLOR_AXIS)
    ax.grid(axis="y", color=COLOR_GRID, linewidth=1)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(COLOR_GRID)
    # matplotlib's DateFormatter renders in UTC unless told otherwise -- a
    # tz-aware pandas column isn't enough on its own. Without `tz=` here, the
    # ticks would silently show UTC clock time even while the subtitle above
    # claims a local zone.
    ax.xaxis.set_major_formatter(mdates.DateFormatter(tick_format, tz=first_ts.tzinfo))
    ax.tick_params(axis="both", length=0, labelsize=9, colors=COLOR_AXIS)

    if source:
        fig.text(0.01, 0.01, source, fontsize=8.5, color=COLOR_MUTED, va="bottom")

    plt.tight_layout(rect=[0, 0.05, 1, 0.78])
    _save(fig, output_path)


def _save(fig, output_path, tight=True):
    import os
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight" if tight else None)
    plt.close(fig)
    print(f"Saved {output_path}")
