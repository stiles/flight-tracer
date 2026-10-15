"""Pixel-level regression tests for rendered maps and charts.

Each case renders through the real plot functions -- same fonts (bundled
Inter), sizes and DPI as the CLI -- and compares the PNG with a committed
baseline in tests/baseline_images/. The basemap is a synthetic raster so the
tests never touch the network and tile changes upstream can't break them.

When a change to the output is intended, regenerate and review the baselines:

    FLIGHT_TRACER_UPDATE_BASELINES=1 python -m pytest tests/test_visual.py

On failure, the new render and a diff image are written to
tests/visual_results/ (ignored by git; uploaded as a CI artifact).
"""

import math
import os
import shutil
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from matplotlib.testing.compare import compare_images
from shapely.geometry import Point

from flight_tracer import viz

HERE = Path(__file__).parent
BASELINES = HERE / "baseline_images"
RESULTS = HERE / "visual_results"
UPDATE = os.environ.get("FLIGHT_TRACER_UPDATE_BASELINES") == "1"

# RMS difference on a 0-255 scale. Renders are pixel-identical across the
# matplotlib releases we support (its wheels all bundle FreeType 2.6.1), so
# this only absorbs incidental antialiasing noise. Keep it tight: resizing
# the endpoint markers on a full 1920x1080 map scores only about 2.5.
TOLERANCE = 0.5

START = pd.Timestamp("2026-10-03T08:45:00Z")
LOCAL_TZ = "America/Los_Angeles"


def _frame(lons, lats, times, leg_id=1, call_sign="N224LA", icao="a1f0d8"):
    n = len(lons)
    steps = np.linspace(0, 1, n)
    gdf = gpd.GeoDataFrame(
        {
            "point_time_utc": times,
            "altitude": np.round(450 + 900 * np.sin(math.pi * steps) + 150 * np.sin(9 * math.pi * steps)),
            "ground_speed": np.round(70 + 35 * np.sin(5 * math.pi * steps), 1),
            "icao": icao,
            "call_sign": call_sign,
            "leg_id": leg_id,
            "flight_leg": f"{call_sign}_leg{leg_id}",
        },
        geometry=[Point(x, y) for x, y in zip(lons, lats)],
        crs="EPSG:4326",
    )
    gdf["point_time_local"] = gdf["point_time_utc"].dt.tz_convert(LOCAL_TZ)
    return gdf


def round_trip():
    """A patrol loop that ends ~100 m from where it started, with one gap."""
    n = 140
    t = np.linspace(0, 2 * math.pi, n)
    lons = -118.30 + 0.11 * np.sin(t) + 0.03 * np.sin(3 * t)
    lats = 34.05 + 0.06 * np.sin(2 * t) / 2 + 0.02 * (1 - np.cos(t))
    lons[-1] += 0.0008
    times = pd.Series(START + pd.to_timedelta(np.arange(n) * 30, unit="s"))
    keep = np.r_[0:70, 90:n]  # 10 minutes without positions -> dashed gap.
    return _frame(lons[keep], lats[keep], times.iloc[keep].reset_index(drop=True))


def point_to_point(leg_id=1, call_sign="N224LA", reverse=False, offset_minutes=0):
    n = 90
    steps = np.linspace(0, 1, n)
    lons = -118.40 + (1.24 * steps)
    lats = 33.94 - (1.21 * steps) + 0.12 * np.sin(math.pi * steps)
    if reverse:
        lons, lats = lons[::-1], lats[::-1] - 0.05
    times = pd.Series(START + pd.Timedelta(minutes=offset_minutes)
                      + pd.to_timedelta(np.arange(n) * 40, unit="s"))
    return _frame(lons, lats, times, leg_id=leg_id, call_sign=call_sign)


def two_legs():
    first = point_to_point(1, "FDX9756")
    second = point_to_point(2, "FDX9797", reverse=True, offset_minutes=180)
    return gpd.GeoDataFrame(pd.concat([first, second], ignore_index=True), crs="EPSG:4326")


def _fake_draw_basemap(ax, provider, zoom=None):
    """Deterministic stand-in for map tiles: gray land, water and a street grid."""
    west, east = ax.get_xlim()
    south, north = ax.get_ylim()
    h, w = 270, 480
    ys, xs = np.mgrid[0:h, 0:w]
    raster = np.full((h, w, 3), 0.95)
    raster[ys > 0.55 * h + 0.25 * xs] = (0.86, 0.87, 0.88)  # "Ocean" in the lower left.
    streets = ((xs % 40) < 2) | ((ys % 30) < 2)
    raster[streets] = 1.0
    ax.imshow(raster, extent=(west, east, south, north), interpolation="nearest", zorder=0)


@pytest.fixture(autouse=True)
def offline_basemap(monkeypatch):
    monkeypatch.setattr(viz, "_draw_basemap", _fake_draw_basemap)


CASES = {
    "map_round_trip_16x9": lambda path: viz.plot_map(
        round_trip(), None, "N224LA — Patrol loop", viz.format_time_span(round_trip()),
        "ADS-B Exchange", path, labels=[{"lat": 34.0369, "lon": -118.2337, "text": "Hooper Heliport"}]),
    "map_point_to_point_9x16": lambda path: viz.plot_map(
        point_to_point(), None, "N224LA — Los Angeles to San Diego",
        viz.format_time_span(point_to_point()), "ADS-B Exchange", path, aspect_ratio="9:16"),
    "map_overview_16x9": lambda path: viz.plot_map(
        two_legs(), None, "N868FD — 2 legs", viz.format_time_span(two_legs()), "ADS-B Exchange", path,
        leg_labels={"FDX9756_leg1": "FDX9756 – Oct 03, 08:45 UTC",
                    "FDX9797_leg2": "FDX9797 – Oct 03, 11:45 UTC"}),
    "altitude_16x9": lambda path: viz.plot_series(
        round_trip(), "altitude", "Altitude", "Feet", path, source="Source: ADS-B Exchange"),
    "speed_9x16": lambda path: viz.plot_series(
        round_trip(), "ground_speed", "Ground speed", "Knots", path,
        source="Source: ADS-B Exchange", aspect_ratio="9:16"),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_render_matches_baseline(name, tmp_path):
    actual = tmp_path / f"{name}.png"
    CASES[name](str(actual))
    expected = BASELINES / f"{name}.png"

    if UPDATE:
        BASELINES.mkdir(exist_ok=True)
        shutil.copyfile(actual, expected)
        return
    if not expected.exists():
        pytest.fail(f"No baseline for {name}. Generate one with "
                    "FLIGHT_TRACER_UPDATE_BASELINES=1 python -m pytest tests/test_visual.py")

    failure = compare_images(str(expected), str(actual), tol=TOLERANCE)
    if failure is None:
        return
    RESULTS.mkdir(exist_ok=True)
    for produced in tmp_path.glob(f"{name}*.png"):
        shutil.copyfile(produced, RESULTS / produced.name)
    pytest.fail(f"{name} differs from its baseline. Review {RESULTS / actual.name} and its "
                f"-failed-diff.png; if the change is intended, regenerate the baselines.\n{failure}")
