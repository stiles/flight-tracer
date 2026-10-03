"""Identified, cached requests for OSM's community tile service.

Only tiles needed for the current map are requested, sequentially. This
cache is separate from Contextily's process-local cache and old error tiles.
"""

import base64
import json
import math
import os
import re
import tempfile
import time
from email.utils import parsedate_to_datetime
from io import BytesIO
from itertools import islice
from pathlib import Path

import mercantile
import numpy as np
import requests
from PIL import Image

WEEK = 7 * 24 * 60 * 60
WORLD = 2 * math.pi * 6378137


def _cache_root():
    root = os.environ.get("FLIGHT_TRACER_CACHE_DIR")
    if not root:
        root = str(Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "flight-tracer")
    return Path(root) / "osm-v1"


def _decode_tile(content):
    with Image.open(BytesIO(content)) as image:
        if image.format != "PNG" or image.size != (256, 256):
            raise ValueError("OSM returned an unexpected tile image")
        array = np.asarray(image.convert("RGB"))
    # OSM's denial tile has tall black/yellow warning stripes. Detect that
    # signature even when a proxy returns the error image with HTTP 200.
    yellow = (array[:, :, 0] > 245) & (array[:, :, 1] > 245) & (array[:, :, 2] < 15)
    black = (array.max(axis=2) < 30)
    if np.any((yellow.sum(axis=0) > 40) & (black.sum(axis=0) > 40)):
        raise ValueError("OSM returned an access-blocked image; no map tiles were drawn")
    return array


def _ttl(headers, default=WEEK):
    control = headers.get("Cache-Control", "").lower()
    if "no-cache" in control:
        return 0
    match = re.search(r"max-age\s*=\s*(\d+)", control)
    if match:
        return max(0, int(match.group(1)) - int(headers.get("Age", "0")))
    if headers.get("Expires"):
        try:
            return max(0, parsedate_to_datetime(headers["Expires"]).timestamp() - time.time())
        except (ValueError, TypeError, OverflowError):
            pass
    return default


def _tile(tile):
    from . import __version__

    path = _cache_root() / str(tile.z) / str(tile.x) / f"{tile.y}.json"
    cached = None
    try:
        cached = json.loads(path.read_text())
        content = base64.b64decode(cached["png"], validate=True)
        array = _decode_tile(content)
        if time.time() < cached["expires"]:
            return array
    except (OSError, ValueError, KeyError, TypeError):
        cached = None

    headers = {"User-Agent": f"FlightTracer/{__version__} (+https://github.com/stiles/flight-tracer)"}
    if cached:
        if cached.get("etag"):
            headers["If-None-Match"] = cached["etag"]
        if cached.get("modified"):
            headers["If-Modified-Since"] = cached["modified"]
    url = f"https://tile.openstreetmap.org/{tile.z}/{tile.x}/{tile.y}.png"
    # No retries on denial or throttling; let the renderer fall back.
    with requests.get(url, headers=headers, timeout=30) as response:
        response.raise_for_status()
        if response.status_code == 304:
            if not cached:
                raise ValueError("OSM returned 304 without a cached tile")
        elif response.status_code == 200:
            content = response.content
            array = _decode_tile(content)
        else:
            raise ValueError(f"Unexpected OSM response: {response.status_code}")
        ttl = _ttl(response.headers, cached.get("ttl", WEEK) if cached else WEEK)
        entry = {
            "png": base64.b64encode(content).decode("ascii"),
            "expires": time.time() + ttl, "ttl": ttl,
            "etag": response.headers.get("ETag", cached.get("etag") if cached else None),
            "modified": response.headers.get("Last-Modified", cached.get("modified") if cached else None),
        }
        if "no-store" in response.headers.get("Cache-Control", "").lower():
            path.unlink(missing_ok=True)
            return array

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(entry, stream)
        temporary.replace(path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    return array


def bounds2img(west, south, east, north, zoom=None):
    """Fetch only the visible XYZ tiles and return a Web Mercator mosaic."""
    if zoom is None:
        zoom = max(0, min(19, math.ceil(math.log2(2 * WORLD / max(east - west, north - south)))))
    if not isinstance(zoom, int) or not 0 <= zoom <= 19:
        raise ValueError("OSM zoom must be an integer from 0 to 19")
    def lon(x):
        return x / WORLD * 360
    def lat(y):
        return math.degrees(math.atan(math.sinh(y / 6378137)))
    tiles = list(islice(mercantile.tiles(lon(west), lat(south), lon(east), lat(north), zoom), 65))
    if not tiles or len(tiles) > 64:
        raise ValueError("OSM map requires too many tiles; use a lower zoom or another basemap")
    xmin, xmax = min(t.x for t in tiles), max(t.x for t in tiles)
    ymin, ymax = min(t.y for t in tiles), max(t.y for t in tiles)
    mosaic = np.empty(((ymax - ymin + 1) * 256, (xmax - xmin + 1) * 256, 3), dtype=np.uint8)
    for tile in tiles:
        x, y = (tile.x - xmin) * 256, (tile.y - ymin) * 256
        mosaic[y:y + 256, x:x + 256] = _tile(tile)
    upper_left = mercantile.xy_bounds(xmin, ymin, zoom)
    lower_right = mercantile.xy_bounds(xmax, ymax, zoom)
    return mosaic, (upper_left.left, lower_right.right, lower_right.bottom, upper_left.top)
