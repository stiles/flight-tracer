"""Named option presets from one user TOML file.

    # ~/.config/flight-tracer/presets.toml
    [default]
    timezone = "auto"

    [social]
    aspect-ratio = "9:16"

[default] always applies; --preset NAME layers a named table on top, and
command-line flags win over both. Presets hold display and output choices
only -- which aircraft and when stays on the command line.
"""

import os
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

# TOML key (spelled like the flag) -> click parameter name.
PRESET_KEYS = {
    "timezone": "timezone",
    "window-timezone": "window_timezone",
    "infer-legs": "infer_legs",
    "leg": "leg",
    "output": "output",
    "filter-ground": "filter_ground",
    "background": "background",
    "formats": "formats",
    "aspect-ratio": "aspect_ratio",
    "gap-minutes": "gap_minutes",
    "no-plots": "no_plots",
    "title": "title",
    "dek": "dek",
    "label": "labels",
    "bucket": "bucket",
    "aws-profile": "aws_profile",
}


def presets_path():
    """$FLIGHT_TRACER_PRESETS, else presets.toml under $XDG_CONFIG_HOME or ~/.config."""
    if os.environ.get("FLIGHT_TRACER_PRESETS"):
        return os.path.expanduser(os.environ["FLIGHT_TRACER_PRESETS"])
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join("~", ".config")
    return os.path.expanduser(os.path.join(base, "flight-tracer", "presets.toml"))


def load_presets(path=None):
    """Every table in the presets file, validated; {} when there is no file."""
    path = path or presets_path()
    try:
        with open(path, "rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Could not read {path}: {exc}") from None

    for name, table in data.items():
        if not isinstance(table, dict):
            raise ValueError(f"{path}: '{name}' must be a table, written [{name}].")
        unknown = sorted(set(table) - set(PRESET_KEYS))
        if unknown:
            raise ValueError(f"{path}: unknown setting{'s' if len(unknown) > 1 else ''} "
                             f"{', '.join(unknown)} in [{name}]. "
                             f"Presets can set: {', '.join(PRESET_KEYS)}.")
    return data


def resolve_preset(name=None, path=None):
    """[default] with [name] on top, keyed by click parameter name."""
    path = path or presets_path()
    presets = load_presets(path)
    if name and name not in presets:
        available = ", ".join(sorted(presets)) or "none"
        raise ValueError(f"No preset named '{name}' in {path}. Available: {available}.")

    merged = {**presets.get("default", {}), **(presets.get(name, {}) if name else {})}
    values = {PRESET_KEYS[key]: value for key, value in merged.items()}
    if isinstance(values.get("labels"), str):
        values["labels"] = [values["labels"]]
    if "output" in values:
        values["output"] = os.path.expanduser(values["output"])
    return values
