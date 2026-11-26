#!/usr/bin/env python3
"""Rebuild the images embedded in the docs.

    python scripts/docs_images.py            # re-render every image
    python scripts/docs_images.py --pin      # point README URLs at the commit
                                             # that last changed each image

Rendering needs live ADS-B Exchange data and, for Mapbox backgrounds, a
MAPBOX_ACCESS_TOKEN in the environment, so this is a manual task and not part
of CI. Because the data is fetched live, check each image by eye before you
commit it.

Workflow when an image changes:

1. Run this script and look at the result.
2. Commit the new image.
3. Run it again with --pin and commit the README.

Pinning is a separate step because the SHA only exists once the image is
committed. The README links to a SHA, not `main`, so the URL changes whenever
the image does and no cache can serve the old one.

To add an image, add an entry to IMAGES.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://raw.githubusercontent.com/stiles/flight-tracer"

# One entry per embedded image. `args` is the full flight-tracer command line
# after the executable, `produces` is the file inside the run folder to copy,
# and `needs_mapbox` makes the script check for a token before fetching.
IMAGES = [
    {
        "path": "docs/images/flight-map.png",
        "doc": "README.md",
        "args": [
            "trace", "--icao", "a1f0d8", "--date", "2026-10-03", "--leg", "4",
            "--background", "mapbox-light", "--timezone", "America/Los_Angeles",
        ],
        "produces": "map.png",
        "needs_mapbox": True,
    },
]


def render(image):
    """Run flight-tracer for one image and copy the result into the repo."""
    if image["needs_mapbox"] and not os.environ.get("MAPBOX_ACCESS_TOKEN", "").strip():
        sys.exit(f"{image['path']} uses a Mapbox background: set MAPBOX_ACCESS_TOKEN first.")
    with tempfile.TemporaryDirectory() as out:
        command = [sys.executable, "-m", "flight_tracer.cli", *image["args"], "--output", out]
        print("$", " ".join(command))
        subprocess.run(command, check=True, cwd=ROOT)
        found = sorted(Path(out).rglob(image["produces"]))
        if not found:
            sys.exit(
                f"The run wrote no {image['produces']}. Read the output above: "
                "ADS-B Exchange may have returned no data for this aircraft and "
                "date, or the command's --leg may not exist."
            )
        if len(found) > 1:
            sys.exit(
                f"Expected one {image['produces']} but the run wrote "
                f"{[str(p.relative_to(out)) for p in found]}. Narrow the "
                "command's --leg selection."
            )
        target = ROOT / image["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(found[0], target)
        print("wrote", image["path"])


def last_commit(path):
    """SHA of the commit that last changed `path`, or None if it has none."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", path],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip() or None


def pin(image):
    """Rewrite the doc's URL for this image to the SHA of its last commit."""
    sha = last_commit(image["path"])
    if sha is None:
        sys.exit(f"{image['path']} isn't committed yet. Commit it, then pin.")
    doc = ROOT / image["doc"]
    text = doc.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(REPO_URL) + r"/[^/\s)]+(?:/[^/\s)]+)*?/" + re.escape(image["path"]))
    new = f"{REPO_URL}/{sha}/{image['path']}"
    updated, count = pattern.subn(new, text)
    if count == 0:
        sys.exit(f"No URL for {image['path']} found in {image['doc']}.")
    if updated == text:
        print(f"{image['doc']} already points at {sha[:7]}")
        return
    doc.write_text(updated, encoding="utf-8")
    print(f"{image['doc']}: {image['path']} now pinned to {sha[:7]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pin", action="store_true",
                        help="rewrite doc URLs to the SHA of each image's last commit "
                             "instead of rendering")
    args = parser.parse_args()
    for image in IMAGES:
        (pin if args.pin else render)(image)


if __name__ == "__main__":
    main()
