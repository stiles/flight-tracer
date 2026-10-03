import unittest
from unittest.mock import patch

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from click.testing import CliRunner
from shapely.geometry import Point

from flight_tracer.cli import cli
from flight_tracer.viz import (
    COLOR_FLIGHT, WORLD_WIDTH, _coverage_segments, _draw_coverage,
    _project_map_data, plot_map,
)


class TestCoverage(unittest.TestCase):
    def points(self):
        return gpd.GeoDataFrame({
            "icao": ["abed10"] * 4,
            "leg_id": [1] * 4,
            "flight_leg": ["FDX9756_leg1"] * 4,
            "call_sign": ["FDX9756"] * 4,
            "point_time_utc": pd.to_datetime([
                "2026-09-26T20:00:00Z", "2026-09-26T20:00:20Z",
                "2026-09-27T00:00:00Z", "2026-09-27T00:00:20Z",
            ]),
        }, geometry=[Point(x, 45) for x in [170, 179, -179, -170]], crs=4326)

    def test_gap_crosses_dateline_and_is_dashed_only(self):
        points = self.points()
        segments = _coverage_segments(points, 5)
        self.assertEqual(segments.coverage_gap.tolist(), [False, True, False])
        self.assertEqual(segments.geometry.iloc[1].geom_type, "MultiLineString")
        _, projected = _project_map_data(points, segments)
        fig, ax = plt.subplots()
        try:
            _draw_coverage(ax, projected, {}, False)
            collection = ax.collections[0]
            self.assertEqual([style[1] is not None for style in collection.get_linestyles()],
                             [False, True, True, False])
            for segment in collection.get_segments():
                self.assertLess(abs(segment[-1][0] - segment[0][0]), WORLD_WIDTH / 10)
        finally:
            plt.close(fig)

    def test_threshold_sorting_and_no_cross_leg_or_aircraft_connections(self):
        points = self.points()
        self.assertFalse(_coverage_segments(points.iloc[::-1], 240).coverage_gap.any())
        points.loc[2:, "leg_id"] = 2
        self.assertEqual(len(_coverage_segments(points, 5)), 2)
        points.loc[2:, "leg_id"] = 1
        points.loc[2:, "icao"] = "other"
        self.assertEqual(len(_coverage_segments(points, 5)), 2)
        for threshold in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                _coverage_segments(points, threshold)

    def test_legend_explains_gap_and_disappears_without_gaps(self):
        for threshold, expected in ((5, True), (240, False)):
            with patch("flight_tracer.viz._add_basemap", return_value=None), \
                 patch("flight_tracer.viz._save") as save:
                plot_map(self.points(), None, "Test", "", "Test", "unused.png",
                         gap_minutes=threshold)
                fig = save.call_args.args[0]
                try:
                    labels = [label.get_text() for label in fig.legends[0].get_texts()]
                    self.assertEqual("Tracking gap (approximate connection)" in labels, expected)
                finally:
                    plt.close(fig)

    def test_cli_passes_threshold_for_single_and_multi_leg_maps(self):
        for multiple in (False, True):
            points = self.points()
            if multiple:
                points.loc[2:, "leg_id"] = 2
            renderer = "_render_all_legs" if multiple else "_render_flight"
            with patch("flight_tracer.cli.FlightTracer.get_traces", return_value=points), \
                 patch("flight_tracer.cli.FlightTracer.process_flight_data", return_value=points), \
                 patch("flight_tracer.cli." + renderer, return_value={}) as render:
                result = CliRunner().invoke(cli, ["trace", "--icao", "abed10", "--leg", "all",
                                                  "--gap-minutes", "2", "--aspect-ratio", "9:16"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(render.call_args.kwargs["gap_minutes"], 2)
                self.assertEqual(render.call_args.kwargs["aspect_ratio"], "9:16")
        result = CliRunner().invoke(cli, ["trace", "--icao", "abed10", "--gap-minutes", "0"])
        self.assertNotEqual(result.exit_code, 0)
