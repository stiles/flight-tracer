import os
import tempfile
import unittest
from unittest.mock import patch

import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
from shapely.geometry import Point

from flight_tracer.viz import plot_map, plot_series, format_time_span


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
            with patch("flight_tracer.viz._add_basemap", return_value=None):
                plot_map(gdf, None, "Test headline", "Test dek", "Test source",
                         output_path, figsize=(10, 7.5))

            from PIL import Image
            with Image.open(output_path) as im:
                width, height = im.size

        expected_w, expected_h = 10 * 200, 7.5 * 200  # figsize * dpi
        self.assertEqual((width, height), (expected_w, expected_h))

    def test_fixed_frames_and_map_panel_survive_expanded_tile_bounds(self):
        gdf = self._make_gdf([-118.41, -118.40, -118.42], [34.25, 34.27, 34.25])
        def expanded_tiles(ax, *args, **kwargs):
            # Reproduce contextily's tile-aligned expansion that caused the
            # map to shrink, despite the correctly sized PNG canvas.
            ax.set_xlim(-14e6, -12e6)
            ax.set_ylim(3e6, 5e6)
            return "Esri"
        for ratio, size in (("16:9", (1920, 1080)), ("9:16", (1080, 1920))):
            with self.subTest(ratio=ratio), tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "map.png")
                from flight_tracer.viz import _save
                captured = []
                def inspect_save(fig, output_path, tight):
                    fig.canvas.draw()
                    ax = fig.axes[0]
                    self.assertAlmostEqual(ax.get_position().width, 0.95, places=6)
                    self.assertAlmostEqual(ax.get_position().height,
                                           ax.get_position(original=True).height, places=6)
                    renderer = fig.canvas.get_renderer()
                    for text in fig.texts:
                        bounds = text.get_window_extent(renderer)
                        self.assertGreaterEqual(bounds.x0, 0)
                        self.assertLessEqual(bounds.x1, fig.bbox.width)
                        self.assertGreaterEqual(bounds.y0, 0)
                        self.assertLessEqual(bounds.y1, fig.bbox.height)
                    captured.append(True)
                    _save(fig, output_path, tight)
                with patch("flight_tracer.viz._add_basemap", side_effect=expanded_tiles), \
                     patch("flight_tracer.viz._save", side_effect=inspect_save):
                    plot_map(gdf, None, "N229LA — AEROSPATIALE AS-350 Ecureuil",
                             format_time_span(gdf), "ADS-B Exchange", path, aspect_ratio=ratio)
                from PIL import Image
                with Image.open(path) as im:
                    self.assertEqual(im.size, size)
                self.assertTrue(captured)

    def test_chart_frames(self):
        df = pd.DataFrame({"point_time_utc": pd.date_range("2026-10-03", periods=4, freq="h", tz="UTC"),
                           "altitude": [10, 30, 20, 15]})
        from PIL import Image
        for ratio, size in (("16:9", (1920, 1080)), ("9:16", (1080, 1920))):
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "chart.png")
                plot_series(df, "altitude", "Altitude", "Feet", path, aspect_ratio=ratio)
                with Image.open(path) as im:
                    self.assertEqual(im.size, size)

    def test_full_topographic_credit_fits_below_map_without_overlay(self):
        from flight_tracer.viz import resolve_basemap
        gdf = self._make_gdf([-118.41, -118.40], [34.25, 34.27])
        _, credit = resolve_basemap("esri-topo")
        for ratio in ("16:9", "9:16"):
            with patch("flight_tracer.viz.ctx.add_basemap") as tiles, \
                 patch("flight_tracer.viz._save") as save:
                plot_map(gdf, None, "N229LA", format_time_span(gdf), "ADS-B Exchange",
                         "unused.png", background="esri-topo", aspect_ratio=ratio)
                fig = save.call_args.args[0]
                try:
                    fig.canvas.draw()
                    self.assertFalse(tiles.call_args.kwargs["attribution"])
                    footer = fig.texts[-1]
                    self.assertIn(credit, " ".join(footer.get_text().split()))
                    box = footer.get_window_extent(fig.canvas.get_renderer())
                    self.assertLess(box.y1, fig.axes[0].get_window_extent().y0)
                    self.assertGreaterEqual(box.x0, 0)
                    self.assertLessEqual(box.x1, fig.bbox.width)
                    self.assertGreaterEqual(box.y0, 0)
                finally:
                    plt.close(fig)


class TestReadableDates(unittest.TestCase):
    def span(self, start, end, zone=None):
        df = pd.DataFrame({"point_time_utc": pd.to_datetime([start, end], utc=True)})
        if zone:
            df["point_time_local"] = df.point_time_utc.dt.tz_convert(zone)
        return format_time_span(df)

    def test_same_day_and_overnight(self):
        self.assertEqual(self.span("2026-10-03T15:37:53Z", "2026-10-03T16:27:40Z"),
                         "Oct. 3, 2026 · 3:37–4:27 p.m. UTC")
        self.assertEqual(self.span("2026-09-26T20:17:17Z", "2026-09-27T10:51:39Z"),
                         "Sept. 26–27, 2026 · 8:17 p.m.–10:51 a.m. UTC")

    def test_year_boundary_and_local_utc_dates(self):
        span = self.span("2026-12-31T23:00:00Z", "2027-01-01T01:00:00Z", "America/Los_Angeles")
        self.assertIn("Dec. 31, 2026 · 3:00–5:00 p.m. PST", span)
        self.assertIn("Dec. 31, 2026–Jan. 1, 2027", span)
        self.assertIn("UTC", span)

    def test_dst_change_identifies_both_zones(self):
        span = self.span("2026-11-01T08:30:00Z", "2026-11-01T09:30:00Z", "America/Los_Angeles")
        self.assertIn("1:30 a.m. PDT–1:30 a.m. PST", span)


if __name__ == "__main__":
    unittest.main()
