import os
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from click.testing import CliRunner

from flight_tracer.cli import cli
from flight_tracer.saved import load_saved_trace

CSV = """point_time_utc,lat,lon,altitude,ground_speed,icao,call_sign,squawk,leg_id,flight_leg,position_source,is_stale
2026-09-16 00:00:00+00:00,34.0,-118.0,1000,80.0,123456,N1,0123,1,N1_leg1,adsb_icao,False
2026-09-16 00:01:00.500000+00:00,34.1,-118.1,1200,85.0,123456,N1,0123,1,N1_leg1,adsb_icao,True
"""


def write_run(folder, csv=CSV):
    with open(os.path.join(folder, "trace.csv"), "w") as handle:
        handle.write(csv)


class TestRender(unittest.TestCase):
    def test_load_keeps_identifiers_as_text_and_applies_timezone(self):
        with tempfile.TemporaryDirectory() as folder:
            write_run(folder)
            gdf = load_saved_trace(folder, timezone="America/Los_Angeles")
        self.assertEqual(gdf["icao"].iloc[0], "123456")
        self.assertEqual(gdf["squawk"].iloc[0], "0123")
        self.assertEqual(gdf["is_stale"].tolist(), [False, True])
        self.assertEqual(gdf["leg_detection"].iloc[0], "unknown")
        self.assertEqual(gdf["point_time_local"].iloc[0].hour, 17)
        self.assertEqual(gdf.crs.to_epsg(), 4326)

    def test_missing_csv_is_a_clear_error(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(FileNotFoundError, "csv"):
                load_saved_trace(folder)

    def test_render_writes_images_elsewhere_and_leaves_data_alone(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as out:
            write_run(folder)
            before = open(os.path.join(folder, "trace.csv")).read()
            with patch("flight_tracer.cli._plot_flight", return_value={"map": "m"}) as plot:
                result = CliRunner().invoke(cli, ["render", folder, "--output", out,
                                                  "--aspect-ratio", "9:16", "--timezone", "utc"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(plot.call_args.args[3], out)
            self.assertEqual(plot.call_args.args[-1], "9:16")
            self.assertEqual(open(os.path.join(folder, "trace.csv")).read(), before)
            self.assertEqual(sorted(os.listdir(folder)), ["trace.csv"])

    def test_render_rejects_missing_csv_and_mapbox_token(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertNotEqual(CliRunner().invoke(cli, ["render", folder]).exit_code, 0)
            write_run(folder)
            with patch.dict(os.environ, {"MAPBOX_ACCESS_TOKEN": ""}):
                result = CliRunner().invoke(cli, ["render", folder, "--background", "mapbox"])
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("MAPBOX_ACCESS_TOKEN", result.output)

    def test_multi_leg_renders_overview_and_each_leg(self):
        csv = CSV + "2026-09-16 01:00:00+00:00,35.0,-119.0,900,70.0,123456,N2,0123,2,N2_leg2,adsb_icao,False\n"
        with tempfile.TemporaryDirectory() as folder:
            write_run(folder, csv)
            with patch("flight_tracer.cli._plot_overview", return_value="o") as overview, \
                 patch("flight_tracer.cli._plot_flight", return_value={}) as plot:
                result = CliRunner().invoke(cli, ["render", folder])
            self.assertEqual(result.exit_code, 0, result.output)
            overview.assert_called_once()
            self.assertEqual(plot.call_count, 2)


if __name__ == "__main__":
    unittest.main()
