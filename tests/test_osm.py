import io
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import matplotlib.pyplot as plt
import mercantile
import numpy as np
import requests
from PIL import Image

from flight_tracer import osm
from flight_tracer.viz import _add_basemap, _draw_basemap, resolve_basemap, WORLD_WIDTH


def png(blocked=False):
    array = np.full((256, 256, 3), 220, dtype=np.uint8)
    if blocked:
        for y in range(256):
            array[y, 10:20] = (255, 255, 0) if y % 20 < 10 else (0, 0, 0)
    stream = io.BytesIO()
    Image.fromarray(array).save(stream, format="PNG")
    return stream.getvalue()


def response(status=200, content=None, headers=None):
    result = MagicMock()
    result.__enter__.return_value = result
    result.status_code = status
    result.content = content if content is not None else png()
    result.headers = headers or {}
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError(f"HTTP {status}")
    return result


class TestOSMTiles(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"FLIGHT_TRACER_CACHE_DIR": self.temp.name})
        self.env.start()
        self.tile = mercantile.Tile(1, 1, 2)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_identified_request_and_persistent_cache(self):
        with patch("flight_tracer.osm.requests.get", return_value=response()) as get:
            first = osm._tile(self.tile)
            second = osm._tile(self.tile)
        self.assertEqual(get.call_count, 1)
        self.assertTrue(np.array_equal(first, second))
        self.assertEqual(get.call_args.args[0], "https://tile.openstreetmap.org/2/1/1.png")
        headers = get.call_args.kwargs["headers"]
        self.assertIn("FlightTracer/", headers["User-Agent"])
        self.assertIn("https://github.com/stiles/flight-tracer", headers["User-Agent"])
        self.assertNotIn("Cache-Control", headers)
        entry = json.loads(next(osm._cache_root().rglob("*.json")).read_text())
        self.assertEqual(entry["ttl"], osm.WEEK)

    def test_expired_cache_uses_conditional_request(self):
        replies = [response(headers={"ETag": '"abc"', "Cache-Control": "max-age=10"}),
                   response(304, headers={"Cache-Control": "max-age=20"})]
        with patch("flight_tracer.osm.requests.get", side_effect=replies) as get:
            with patch("flight_tracer.osm.time.time", return_value=100):
                original = osm._tile(self.tile)
            with patch("flight_tracer.osm.time.time", return_value=111):
                refreshed = osm._tile(self.tile)
            with patch("flight_tracer.osm.time.time", return_value=120):
                osm._tile(self.tile)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args.kwargs["headers"]["If-None-Match"], '"abc"')
        self.assertTrue(np.array_equal(original, refreshed))

    def test_denial_status_and_error_images_are_not_cached_or_retried(self):
        for reply in (response(403), response(429), response(content=png(True)),
                      response(content=b"<html>blocked</html>")):
            with patch("flight_tracer.osm.requests.get", return_value=reply) as get:
                with self.assertRaises((requests.HTTPError, ValueError, OSError)):
                    osm._tile(self.tile)
                self.assertEqual(get.call_count, 1)
                self.assertEqual(list(osm._cache_root().rglob("*.json")), [])

    def test_no_store_and_age(self):
        self.assertEqual(osm._ttl({"Cache-Control": "max-age=100", "Age": "25"}), 75)
        with patch("flight_tracer.osm.requests.get", return_value=response(headers={"Cache-Control": "no-store"})):
            osm._tile(self.tile)
        self.assertEqual(list(osm._cache_root().rglob("*.json")), [])

    def test_mosaic_geography_and_fetch_limit(self):
        with patch("flight_tracer.osm._tile", return_value=np.zeros((256, 256, 3), dtype=np.uint8)) as tile:
            array, extent = osm.bounds2img(-1000, -1000, 1000, 1000, zoom=2)
            self.assertEqual(array.shape, (512, 512, 3))
            self.assertEqual(tile.call_count, 4)
            self.assertLess(extent[0], -1000)
            self.assertGreater(extent[1], 1000)
            with self.assertRaisesRegex(ValueError, "too many tiles"):
                osm.bounds2img(-WORLD_WIDTH / 2, -WORLD_WIDTH / 2, WORLD_WIDTH / 2, WORLD_WIDTH / 2, zoom=5)
            self.assertEqual(tile.call_count, 4)

    def test_dateline_uses_osm_cache_for_both_world_strips(self):
        fig, ax = plt.subplots()
        try:
            half = WORLD_WIDTH / 2
            ax.set_xlim(half - 1000, half + 1000)
            ax.set_ylim(0, 1000)
            def mosaic(w, s, e, n, **kwargs):
                return np.zeros((2, 2, 3)), (w, e, s, n)
            with patch("flight_tracer.viz.osm_bounds2img", side_effect=mosaic) as fetch:
                _draw_basemap(ax, resolve_basemap("osm")[0])
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(ax.get_xlim(), (half - 1000, half + 1000))
        finally:
            plt.close(fig)

    def test_denial_falls_back_before_drawing_any_osm_tiles(self):
        fig, ax = plt.subplots()
        try:
            ax.set_xlim(0, 1000)
            ax.set_ylim(0, 1000)
            with patch("flight_tracer.viz.osm_bounds2img", side_effect=ValueError("access-blocked")), \
                 patch("flight_tracer.viz.ctx.add_basemap") as esri:
                credit = _add_basemap(ax, "osm")
            self.assertEqual(len(ax.images), 0)
            self.assertEqual(credit, resolve_basemap("esri-light")[1])
            self.assertEqual(esri.call_count, 1)
        finally:
            plt.close(fig)
