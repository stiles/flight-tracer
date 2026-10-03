"""Editor-supplied map titles, deks and location labels, saved with a run."""

import json
import os

ANNOTATIONS_FILE = "annotations.json"


def parse_label(value):
    """Turn "LAT,LON,Text" into {"lat", "lon", "text"}. Text may contain commas."""
    parts = [part.strip() for part in str(value).split(",", 2)]
    example = 'e.g. "33.9425,-118.408,LAX"'
    if len(parts) != 3 or not parts[2]:
        raise ValueError(f"Labels take LAT,LON,Text, {example}; got {value!r}")
    try:
        lat, lon = float(parts[0]), float(parts[1])
    except ValueError:
        raise ValueError(f"Label coordinates must be numbers, {example}; got {value!r}") from None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"Label coordinates out of range (lat -90..90, lon -180..180); got {value!r}")
    return {"lat": lat, "lon": lon, "text": parts[2]}


def make_annotations(title=None, dek=None, labels=()):
    return {"title": title or None, "dek": dek or None, "labels": list(labels)}


def write_annotations(folder, annotations):
    """Always written, even when empty, so a rerun clears an earlier run's notes."""
    path = os.path.join(folder, ANNOTATIONS_FILE)
    with open(path, "w") as handle:
        json.dump(annotations, handle, indent=2)
    return path


def read_annotations(folder):
    """Saved annotations, or empty ones for folders written before they existed."""
    path = os.path.join(folder, ANNOTATIONS_FILE)
    try:
        with open(path) as handle:
            saved = json.load(handle)
    except FileNotFoundError:
        saved = {}
    return make_annotations(saved.get("title"), saved.get("dek"),
                            [parse_label(f"{l['lat']},{l['lon']},{l['text']}") for l in saved.get("labels", [])])


def merge_annotations(saved, title=None, dek=None, labels=()):
    """Flags win over saved values; any --label replaces the saved labels."""
    return make_annotations(title or saved["title"], dek or saved["dek"],
                            labels or saved["labels"])
