import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import matplotlib.pyplot as plt
import numpy as np
from click.testing import CliRunner

from flight_tracer.cli import cli
from flight_tracer.viz import (
    MAPBOX_CREDIT, MAPBOX_STYLES, WORLD_WIDTH, _add_basemap,
    _add_mapbox_logo, _draw_basemap, resolve_basemap,
)


class TestMapbox(unittest.TestCase):
    def test_style_urls_and_token_encoding(self):
        with patch.dict(os.environ, {"MAPBOX_ACCESS_TOKEN": "pk.test+&value"}):
            for name, style in MAPBOX_STYLES.items():
                provider, credit = resolve_basemap(name)
                url = provider.build_url(x=1, y=2, z=3)
                self.assertIn(f"/mapbox/{style}/tiles/512/3/1/2@2x", url)
                self.assertIn("access_token=pk.test%2B%26value", url)
                self.assertEqual(credit, MAPBOX_CREDIT)

    def test_missing_token_fails_before_fetch(self):
        with patch.dict(os.environ, {"MAPBOX_ACCESS_TOKEN": ""}), \
             patch("flight_tracer.cli.FlightTracer.get_traces") as fetch:
            result = CliRunner().invoke(cli, ["trace", "--icao", "abed10", "--background", "mapbox"])
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("MAPBOX_ACCESS_TOKEN", result.output)
            fetch.assert_not_called()

    def test_standard_style_is_explicitly_unsupported(self):
        with self.assertRaisesRegex(ValueError, "Standard is not supported"):
            resolve_basemap("mapbox-standard")

    def test_failures_do_not_print_token_and_fallback_has_correct_credit(self):
        secret = "pk.fake-private-test-value"
        fig, ax = plt.subplots()
        output = io.StringIO()
        try:
            with patch.dict(os.environ, {"MAPBOX_ACCESS_TOKEN": secret}), \
                 patch("flight_tracer.viz._draw_basemap", side_effect=[RuntimeError(secret), None]), \
                 redirect_stdout(output):
                credit = _add_basemap(ax, "mapbox-light")
            self.assertNotIn(secret, output.getvalue())
            self.assertIn("falling back", output.getvalue())
            self.assertEqual(credit, resolve_basemap("esri-light")[1])
        finally:
            plt.close(fig)

    def test_mapbox_uses_existing_tiles_and_dateline_wrapping(self):
        with patch.dict(os.environ, {"MAPBOX_ACCESS_TOKEN": "pk.fake"}):
            provider, _ = resolve_basemap("mapbox")
        fig, ax = plt.subplots()
        try:
            ax.set_xlim(0, 1000)
            ax.set_ylim(0, 1000)
            with patch("flight_tracer.viz.ctx.add_basemap") as tiles:
                _draw_basemap(ax, provider)
                self.assertEqual(tiles.call_args.kwargs["source"], provider)
                self.assertFalse(tiles.call_args.kwargs["attribution"])
            half = WORLD_WIDTH / 2
            ax.set_xlim(half - 1000, half + 1000)
            def tile(w, s, e, n, **kwargs):
                self.assertEqual(kwargs["source"], provider)
                return np.zeros((2, 2, 3)), (w, e, s, n)
            with patch("flight_tracer.viz.ctx.bounds2img", side_effect=tile) as tiles:
                _draw_basemap(ax, provider)
                self.assertEqual(tiles.call_count, 2)
        finally:
            plt.close(fig)

    def test_bundled_logo_renders_within_figure(self):
        fig = plt.figure(figsize=(5.4, 9.6))
        try:
            _add_mapbox_logo(fig, 0.05)
            fig.canvas.draw()
            ax = fig.axes[0]
            self.assertEqual(len(ax.images), 1)
            self.assertGreater(ax.get_position().y0, 0.05)
            self.assertLess(ax.get_position().y1, 1)
        finally:
            plt.close(fig)
