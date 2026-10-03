import json
import os
import tempfile
import unittest
from unittest.mock import patch

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from click.testing import CliRunner
from shapely.geometry import Point

from flight_tracer.annotations import (merge_annotations, parse_label, read_annotations,
                                       make_annotations, write_annotations)
from flight_tracer.cli import cli
from flight_tracer.viz import WORLD_WIDTH, _project_map_data, plot_map
from tests.test_render import CSV, write_run

LAX = {"lat": 33.9425, "lon": -118.408, "text": "LAX"}


def points(lons, lat=34.0):
    n = len(lons)
    return gpd.GeoDataFrame({
        "icao": ["a40442"] * n, "leg_id": [1] * n, "flight_leg": ["N1_leg1"] * n,
        "call_sign": ["N1"] * n, "leg_detection": ["archive_flags"] * n,
        "point_time_utc": pd.date_range("2026-09-16T00:00:00Z", periods=n, freq="10s"),
    }, geometry=[Point(x, lat) for x in lons], crs=4326)


class TestParseLabel(unittest.TestCase):
    def test_text_may_contain_commas(self):
        self.assertEqual(parse_label(" 34.0, -118.2 , Crash site, Malibu"),
                         {"lat": 34.0, "lon": -118.2, "text": "Crash site, Malibu"})

    def test_rejects_malformed_labels(self):
        for value in ("34,-118", "34,-118,", "north,-118,LAX", "91,-118,X", "34,181,X"):
            with self.assertRaises(ValueError, msg=value):
                parse_label(value)


class TestSavedAnnotations(unittest.TestCase):
    def test_round_trip_and_missing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(read_annotations(folder), make_annotations())
            write_annotations(folder, make_annotations("Title", None, [LAX]))
            self.assertEqual(read_annotations(folder), make_annotations("Title", None, [LAX]))

    def test_flags_override_and_labels_replace(self):
        saved = make_annotations("Saved", "Saved dek", [LAX])
        other = {"lat": 34.0, "lon": -118.0, "text": "Other"}
        merged = merge_annotations(saved, title="New", labels=(other,))
        self.assertEqual(merged, make_annotations("New", "Saved dek", [other]))
        self.assertEqual(merge_annotations(saved), saved)


class TestMapLabels(unittest.TestCase):
    def test_label_extends_extent_and_stays_out_of_legend(self):
        with patch("flight_tracer.viz._add_basemap", return_value=None), \
             patch("flight_tracer.viz._save") as save:
            plot_map(points([-118.0, -117.9]), None, "Custom title", "", "Test", "unused.png",
                     labels=[LAX])
        fig = save.call_args.args[0]
        try:
            ax = fig.axes[0]
            lax_x = gpd.GeoSeries([Point(LAX["lon"], LAX["lat"])], crs=4326).to_crs(3857).x[0]
            self.assertLess(ax.get_xlim()[0], lax_x)
            self.assertIn("LAX", [text.get_text() for text in ax.texts])
            self.assertNotIn("LAX", [text.get_text() for text in fig.legends[0].get_texts()])
            self.assertIn("Custom title", [text.get_text() for text in fig.texts])
        finally:
            plt.close(fig)

    def test_label_wraps_with_route_across_date_line(self):
        marks = gpd.GeoDataFrame({"text": ["Anchor"]}, geometry=[Point(-175, 45)], crs=4326)
        projected, _, wrapped = _project_map_data(points([170, 179]), None, marks)
        self.assertGreater(wrapped.geometry.x[0], WORLD_WIDTH / 2)
        self.assertLess(wrapped.geometry.x[0] - projected.geometry.x.max(), WORLD_WIDTH / 4)


class TestCliAnnotations(unittest.TestCase):
    def test_trace_passes_and_saves_annotations(self):
        gdf = points([-118.0, -117.9])
        with tempfile.TemporaryDirectory() as out, \
             patch("flight_tracer.cli.FlightTracer.get_traces", return_value=gdf), \
             patch("flight_tracer.cli.FlightTracer.process_flight_data", return_value=gdf), \
             patch("flight_tracer.cli._render_flight", return_value={}) as render:
            result = CliRunner().invoke(cli, ["trace", "--icao", "a40442", "--output", out,
                                              "--title", "Helicopter circles Malibu",
                                              "--label", "33.9425,-118.408,LAX"])
            self.assertEqual(result.exit_code, 0, result.output)
            expected = make_annotations("Helicopter circles Malibu", None, [LAX])
            self.assertEqual(render.call_args.kwargs["annotations"], expected)
            (folder,) = os.listdir(out)
            with open(os.path.join(out, folder, "annotations.json")) as handle:
                self.assertEqual(json.load(handle), expected)

    def test_bad_label_is_a_usage_error(self):
        result = CliRunner().invoke(cli, ["trace", "--icao", "a40442", "--label", "34,-118"])
        self.assertEqual(result.exit_code, 2)
        self.assertIn("LAT,LON,Text", result.output)

    def test_render_reuses_saved_annotations_unless_overridden(self):
        with tempfile.TemporaryDirectory() as folder:
            write_run(folder)
            write_annotations(folder, make_annotations("Saved", "Saved dek", [LAX]))
            with patch("flight_tracer.cli._plot_flight", return_value={}) as plot:
                CliRunner().invoke(cli, ["render", folder])
                self.assertEqual(plot.call_args.kwargs, {"title": "Saved", "dek": "Saved dek", "labels": [LAX]})
                result = CliRunner().invoke(cli, ["render", folder, "--title", "New"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(plot.call_args.kwargs["title"], "New")
                self.assertEqual(plot.call_args.kwargs["labels"], [LAX])

    def test_multi_leg_title_goes_on_overview_only(self):
        csv = CSV + "2026-09-16 01:00:00+00:00,35.0,-119.0,900,70.0,123456,N2,0123,2,N2_leg2,adsb_icao,False\n"
        with tempfile.TemporaryDirectory() as folder:
            write_run(folder, csv)
            with patch("flight_tracer.cli._plot_overview", return_value="o") as overview, \
                 patch("flight_tracer.cli._plot_flight", return_value={}) as plot:
                result = CliRunner().invoke(cli, ["render", folder, "--title", "Two hops",
                                                  "--label", "33.9425,-118.408,LAX"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(overview.call_args.kwargs["title"], "Two hops")
            for call in plot.call_args_list:
                self.assertEqual(call.kwargs, {"labels": [LAX]})


if __name__ == "__main__":
    unittest.main()
