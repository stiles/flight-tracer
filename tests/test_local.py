import gzip
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from flight_tracer import FlightTracer
from flight_tracer.cli import cli

TRACE = {
    "icao": "AC4888",
    "r": "N8906K",
    "t": "B38M",
    "desc": "BOEING 737 MAX 8",
    "ownOp": "SOUTHWEST AIRLINES CO",
    "timestamp": 1794787200.0,
    "trace": [
        [0, 39.87, -104.66, 1500, 150, 200, 0, 0, {"flight": "SWA526  "}, "adsb_icao"],
        [60, 39.80, -104.70, 3000, 200, 210, 0, 1200, None, "adsb_icao"],
    ],
}


def write_trace(folder, name="trace_full_ac4888.json", data=TRACE, compress=False):
    path = os.path.join(folder, name)
    payload = json.dumps(data).encode()
    with open(path, "wb") as handle:
        handle.write(gzip.compress(payload) if compress else payload)
    return path


class TestLoadTraceFile(unittest.TestCase):
    def test_plain_and_gzipped_files_read_the_same(self):
        with tempfile.TemporaryDirectory() as folder:
            plain = FlightTracer.load_trace_file(write_trace(folder))
            zipped = FlightTracer.load_trace_file(write_trace(folder, "z.json", compress=True))
        self.assertEqual(len(plain), 2)
        self.assertEqual(plain["icao"].iloc[0], "ac4888")
        self.assertEqual(plain["registration"].iloc[0], "N8906K")
        self.assertTrue(plain[["lat", "lon", "point_time_utc"]].equals(zipped[["lat", "lon", "point_time_utc"]]))

    def test_icao_falls_back_to_filename(self):
        data = {k: v for k, v in TRACE.items() if k != "icao"}
        with tempfile.TemporaryDirectory() as folder:
            raw = FlightTracer.load_trace_file(write_trace(folder, "trace_full_~29962a.json", data))
            self.assertEqual(raw["icao"].iloc[0], "~29962a")
            with self.assertRaisesRegex(ValueError, "no 'icao' field"):
                FlightTracer.load_trace_file(write_trace(folder, "flight.json", data))

    def test_unusable_files_raise(self):
        with tempfile.TemporaryDirectory() as folder:
            bad_json = os.path.join(folder, "bad.json")
            with open(bad_json, "w") as handle:
                handle.write("<html>")
            for path, message in ((bad_json, "not valid JSON"),
                                  (write_trace(folder, "x.json", {"icao": "ac4888"}), "no 'timestamp'"),
                                  (write_trace(folder, "y.json", {**TRACE, "trace": []}), "no trace points")):
                with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                    FlightTracer.load_trace_file(path)


class TestTraceLocal(unittest.TestCase):
    def test_local_file_writes_outputs_without_fetching(self):
        with tempfile.TemporaryDirectory() as folder:
            path = write_trace(folder)
            out = os.path.join(folder, "out")
            with patch("flight_tracer.core.requests.get") as fetch:
                result = CliRunner().invoke(cli, ["trace", "--local", path, "--no-plots", "--output", out])
            self.assertEqual(result.exit_code, 0, result.output)
            fetch.assert_not_called()
            run = os.path.join(out, "ac4888_2026-11-16_2026-11-16")
            self.assertTrue({"trace.csv", "points.geojson", "line.geojson", "summary.json"} <= set(os.listdir(run)))
            with open(os.path.join(run, "selection.json")) as handle:
                self.assertEqual(json.load(handle)["local_files"], [os.path.abspath(path)])

    def test_local_rejects_fetch_options(self):
        with tempfile.TemporaryDirectory() as folder:
            path = write_trace(folder)
            for extra in (["--icao", "a40442"], ["--date", "2026-11-16"], ["--recent"]):
                with self.subTest(extra=extra):
                    result = CliRunner().invoke(cli, ["trace", "--local", path, *extra])
                    self.assertNotEqual(result.exit_code, 0)
                    self.assertIn("don't combine it", result.output)


if __name__ == "__main__":
    unittest.main()
