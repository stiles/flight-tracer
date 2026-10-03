import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import Point

from flight_tracer import FlightTracer
from flight_tracer.geometry import route_geometry
from flight_tracer.viz import WORLD_WIDTH, _draw_basemap, _project_map_data


class TestDateLine(unittest.TestCase):
    def points(self, lons):
        return gpd.GeoDataFrame({
            "icao": ["abed10"] * len(lons),
            "flight_leg": ["FDX9756_leg1"] * len(lons),
            "leg_id": [1] * len(lons),
            "call_sign": ["FDX9756"] * len(lons),
            "point_time_utc": pd.date_range("2026-09-26", periods=len(lons), freq="h", tz="UTC"),
        }, geometry=[Point(lon, 45 + i) for i, lon in enumerate(lons)], crs=4326)

    def test_crossings_both_directions_and_repeated(self):
        for lons in ([170, 179, -179, -160], [-170, -179, 179, 160],
                     [179, -179, 179, -179], [179, 180, -179],
                     [179, -180, -179]):
            with self.subTest(lons=lons):
                geometry = route_geometry(list(self.points(lons).geometry))
                self.assertEqual(geometry.geom_type, "MultiLineString")
                for line in geometry.geoms:
                    xs = [coord[0] for coord in line.coords]
                    self.assertTrue(all(-180 <= x <= 180 for x in xs))
                    self.assertTrue(all(abs(b - a) <= 180 for a, b in zip(xs, xs[1:])))
                first, second = geometry.geoms[0], geometry.geoms[1]
                self.assertAlmostEqual(first.coords[-1][1], second.coords[0][1])

    def test_ordinary_and_single_point_routes(self):
        points = self.points([-118, -117])
        self.assertEqual(route_geometry(list(points.geometry)).geom_type, "LineString")
        self.assertEqual(route_geometry([points.geometry.iloc[0]]).geom_type, "Point")

    def test_export_and_map_window(self):
        points = self.points([170, 179, -179, -160])
        original = points.copy()
        tracer = FlightTracer(aircraft_ids=["abed10"])
        with tempfile.TemporaryDirectory() as tmp:
            _, lines = tracer.write_outputs(points, tmp)
            exported = gpd.read_file(Path(tmp) / "line.geojson")
            self.assertEqual(exported.geometry.iloc[0].geom_type, "MultiLineString")
            self.assertEqual(len(exported), 1)  # the crossing is still one flight leg
        projected, routes, _ = _project_map_data(points, lines)
        self.assertAlmostEqual(projected.total_bounds[2] - projected.total_bounds[0],
                               WORLD_WIDTH * 30 / 360)
        for line in routes.geometry.iloc[0].geoms:
            self.assertLess(line.length, WORLD_WIDTH / 4)
        pd.testing.assert_frame_equal(points, original)

    def test_ordinary_map_coordinates_unchanged(self):
        points = self.points([-118, -117, -116])
        projected, _, _ = _project_map_data(points, None)
        self.assertTrue(projected.geometry.equals(points.to_crs(3857).geometry))

    def test_tiles_wrap_and_share_zoom_without_changing_extent(self):
        half = WORLD_WIDTH / 2
        fig, ax = plt.subplots()
        ax.set_xlim(half - 1e6, half + 2e6)
        ax.set_ylim(1e6, 3e6)
        def tiles(w, s, e, n, **kwargs):
            self.assertGreaterEqual(w, -half)
            self.assertLessEqual(e, half)
            return np.zeros((2, 2, 3)), (w, e, s, n)
        try:
            with patch("flight_tracer.viz.ctx.bounds2img", side_effect=tiles) as fetch:
                _draw_basemap(ax, {"max_zoom": 16})
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(fetch.call_args_list[0].kwargs["zoom"], fetch.call_args_list[1].kwargs["zoom"])
            self.assertEqual(ax.get_xlim(), (half - 1e6, half + 2e6))
            self.assertEqual(ax.get_ylim(), (1e6, 3e6))
            self.assertAlmostEqual(ax.images[0].get_extent()[1], ax.images[1].get_extent()[0])
        finally:
            plt.close(fig)
