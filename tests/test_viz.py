import os
import tempfile
import unittest

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from flight_tracer.viz import plot_map


class TestPlotMapAspect(unittest.TestCase):
    def _make_gdf(self, lons, lats):
        n = len(lons)
        gdf = gpd.GeoDataFrame(
            {
                "point_time_utc": pd.date_range("2026-09-16T00:00:00Z", periods=n, freq="s"),
                "icao": ["a40442"] * n,
                "call_sign": ["N358TV"] * n,
                "leg_id": [1] * n,
                "flight_leg": ["N358TV_leg1"] * n,
            },
            geometry=[Point(x, y) for x, y in zip(lons, lats)],
            crs="EPSG:4326",
        )
        return gdf

    def test_output_matches_requested_figsize_even_when_route_is_square(self):
        # A tight loop -- roughly equal lon/lat extent -- is exactly the shape
        # that made geopandas' equal-aspect axes shrink and the saved PNG come
        # out portrait instead of the requested landscape figsize.
        gdf = self._make_gdf(
            lons=[-118.41, -118.40, -118.41, -118.42, -118.41],
            lats=[34.25, 34.26, 34.27, 34.26, 34.25],
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_path = os.path.join(tmp, "map.png")
            plot_map(gdf, None, "Test headline", "Test dek", "Test source",
                      output_path, figsize=(10, 7.5))

            from PIL import Image
            with Image.open(output_path) as im:
                width, height = im.size

        expected_w, expected_h = 10 * 200, 7.5 * 200  # figsize * dpi
        self.assertEqual((width, height), (expected_w, expected_h))


if __name__ == "__main__":
    unittest.main()
