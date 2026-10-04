import json
import os
import tempfile
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from flight_tracer.annotations import make_annotations, write_annotations
from flight_tracer.cli import cli
from flight_tracer.presets import presets_path, resolve_preset
from flight_tracer.saved import load_saved_trace
from tests.test_annotations import LAX, points
from tests.test_render import write_run

PRESETS = """
[default]
timezone = "UTC"
background = "osm"

[social]
aspect-ratio = "9:16"
output = "~/social"

[lapd]
timezone = "America/Los_Angeles"
label = "33.9425,-118.408,LAX"
dek = "Preset dek"
"""


class PresetFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "presets.toml")
        self.write(PRESETS)
        env = patch.dict(os.environ, {"FLIGHT_TRACER_PRESETS": self.path})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)

    def write(self, text):
        with open(self.path, "w") as handle:
            handle.write(text)


class TestResolvePreset(PresetFile):
    def test_named_table_layers_over_default(self):
        values = resolve_preset("social")
        self.assertEqual(values["background"], "osm")
        self.assertEqual(values["aspect_ratio"], "9:16")
        self.assertEqual(values["output"], os.path.expanduser("~/social"))
        self.assertEqual(resolve_preset("lapd")["labels"], ["33.9425,-118.408,LAX"])
        self.assertEqual(resolve_preset(), {"timezone": "UTC", "background": "osm"})

    def test_errors_name_the_problem(self):
        with self.assertRaisesRegex(ValueError, "Available: default, lapd, social"):
            resolve_preset("print")
        self.write('[default]\naspect_ratio = "9:16"\n')
        with self.assertRaisesRegex(ValueError, r"unknown setting aspect_ratio in \[default\]"):
            resolve_preset()
        self.write("[default\n")
        with self.assertRaisesRegex(ValueError, "Could not read"):
            resolve_preset()

    def test_missing_file_is_empty(self):
        os.remove(self.path)
        self.assertEqual(resolve_preset(), {})

    def test_xdg_location(self):
        with patch.dict(os.environ, {"FLIGHT_TRACER_PRESETS": "", "XDG_CONFIG_HOME": "/cfg"}):
            self.assertEqual(presets_path(), "/cfg/flight-tracer/presets.toml")


class TestTracePresets(PresetFile):
    def run_trace(self, *args):
        gdf = points([-118.0, -117.9])
        out = os.path.join(self.tmp.name, "out")
        with patch("flight_tracer.cli.FlightTracer.get_traces", return_value=gdf), \
             patch("flight_tracer.cli.FlightTracer.process_flight_data", return_value=gdf), \
             patch("flight_tracer.cli._render_flight", return_value={}) as render:
            result = CliRunner().invoke(cli, ["trace", "--icao", "a40442", "--output", out, *args])
        self.assertEqual(result.exit_code, 0, result.output)
        return render.call_args, out

    def test_preset_seeds_defaults_and_flags_win(self):
        call, out = self.run_trace("--preset", "lapd", "--background", "esri-topo")
        self.assertEqual(call.args[4], "esri-topo")
        self.assertEqual(call.args[3], "America/Los_Angeles")
        self.assertEqual(call.kwargs["annotations"], make_annotations(None, "Preset dek", [LAX]))
        (folder,) = os.listdir(out)
        with open(os.path.join(out, folder, "selection.json")) as handle:
            self.assertEqual(json.load(handle)["preset"], "lapd")

    def test_default_table_applies_without_preset(self):
        call, _ = self.run_trace()
        self.assertEqual(call.args[4], "osm")
        self.assertEqual(call.kwargs["aspect_ratio"], "16:9")

    def test_bad_preset_value_is_rejected_like_a_flag(self):
        self.write('[default]\naspect-ratio = "4:3"\n')
        result = CliRunner().invoke(cli, ["trace", "--icao", "a40442"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("4:3", result.output)

    def test_unknown_preset_fails_before_fetching(self):
        with patch("flight_tracer.cli.FlightTracer.get_traces") as fetch:
            result = CliRunner().invoke(cli, ["trace", "--icao", "a40442", "--preset", "print"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("No preset named 'print'", result.output)
        fetch.assert_not_called()


class TestRenderPresets(PresetFile):
    def render(self, folder, *args):
        with patch("flight_tracer.cli._plot_flight", return_value={}) as plot:
            result = CliRunner().invoke(cli, ["render", folder, *args])
        self.assertEqual(result.exit_code, 0, result.output)
        return plot.call_args

    def test_preset_fills_what_the_run_did_not_save(self):
        with tempfile.TemporaryDirectory() as folder:
            write_run(folder)
            call = self.render(folder, "--preset", "social")
            self.assertEqual(call.args[4], "osm")
            self.assertEqual(call.args[6], "9:16")
            self.assertEqual(call.args[3], folder)  # preset output never redirects render
            call = self.render(folder, "--preset", "lapd")
            self.assertEqual(call.kwargs, {"title": None, "dek": "Preset dek", "labels": [LAX]})

    def test_saved_run_outranks_preset(self):
        other = {"lat": 34.0, "lon": -118.0, "text": "Saved"}
        with tempfile.TemporaryDirectory() as folder:
            write_run(folder)
            write_annotations(folder, make_annotations("Saved title", None, [other]))
            with open(os.path.join(folder, "summary.json"), "w") as handle:
                json.dump({"timezone": None}, handle)
            with patch("flight_tracer.cli.load_saved_trace", wraps=load_saved_trace) as load:
                call = self.render(folder, "--preset", "lapd")
            self.assertIsNone(load.call_args.kwargs["timezone"])
            self.assertEqual(call.kwargs, {"title": "Saved title", "dek": "Preset dek", "labels": [other]})


class TestPresetsCommand(PresetFile):
    def test_lists_tables_or_explains_missing_file(self):
        result = CliRunner().invoke(cli, ["presets"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(self.path, result.output)
        self.assertIn("[social] aspect-ratio = '9:16'", result.output)
        os.remove(self.path)
        self.assertIn("No presets file", CliRunner().invoke(cli, ["presets"]).output)


if __name__ == "__main__":
    unittest.main()
