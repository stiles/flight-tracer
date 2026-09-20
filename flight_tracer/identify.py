# flight_tracer/identify.py
"""Turn what a reporter actually has — an N-number, an ICAO hex, or a pasted
ADS-B Exchange URL — into the ICAO hex flight_tracer needs to fetch a trace.
"""

import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs

ICAO_RE = re.compile(r"^[0-9a-fA-F]{6}$")


def parse_adsbx_url(url):
    """Pull an ICAO hex and, if present, a replay date out of a globe.adsbexchange.com URL.

    Handles links like:
        https://globe.adsbexchange.com/?replay=2026-09-16-01:58&icao=a40442&lat=34.251&lon=-118.614&zoom=7.0
        https://globe.adsbexchange.com/?icao=a40442

    Returns a dict: {"icao", "date" (date or None), "time" (str or None), "lat", "lon", "zoom"}.
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    icao = (params.get("icao") or [None])[0]
    if not icao:
        match = re.search(r"icao=([0-9a-fA-F]{6})", url)
        icao = match.group(1) if match else None
    if not icao or not ICAO_RE.match(icao):
        raise ValueError(f"Could not find a 6-character ICAO hex in URL: {url}")

    result = {
        "icao": icao.lower(),
        "date": None,
        "time": None,
        "lat": None,
        "lon": None,
        "zoom": None,
    }

    replay = (params.get("replay") or [None])[0]
    if replay:
        match = re.match(r"(\d{4}-\d{2}-\d{2})-(\d{2}:\d{2})", replay)
        if match:
            result["date"] = datetime.strptime(match.group(1), "%Y-%m-%d").date()
            result["time"] = match.group(2)

    for key in ("lat", "lon", "zoom"):
        value = (params.get(key) or [None])[0]
        if value:
            try:
                result[key] = float(value)
            except ValueError:
                pass

    return result


def resolve_n_number(n_number):
    """Resolve a tail number to its ICAO hex via the FAA registry (hangarbay).

    Returns a dict: {"icao", "n_number", "maker", "model", "owner_name"}.
    Raises ImportError if hangarbay isn't installed, ValueError if the
    N-number isn't found or has no Mode S code on file.
    """
    try:
        import hangarbay as hb
    except ImportError as exc:
        raise ImportError(
            "Resolving an N-number requires the 'hangarbay' package.\n"
            "Install it with:\n"
            "    pip install hangarbay\n"
            "or install flight-tracer with the faa extra:\n"
            "    pip install flight-tracer[faa]"
        ) from exc

    df = hb.search(n_number, skip_age_check=True)
    if df is None or df.empty:
        raise ValueError(f"No FAA registration found for {n_number!r}.")

    row = df.iloc[0]
    icao = str(row.get("mode_s_code_hex", "") or "").strip().lower()
    if not icao:
        raise ValueError(f"FAA record for {n_number!r} has no Mode S / ICAO hex code on file.")

    clean_n_number = str(row.get("n_number", "")).lstrip("N")
    return {
        "icao": icao,
        "n_number": f"N{clean_n_number}",
        "maker": row.get("maker"),
        "model": row.get("model"),
        "owner_name": row.get("owner_name"),
    }


def looks_like_icao(value):
    """True if value looks like a 6-character ICAO hex rather than an N-number."""
    return bool(ICAO_RE.match(value.strip()))


def resolve_timezone(timezone, lat=None, lon=None):
    """Turn a --timezone value into an IANA zone name, or None for UTC-only.

    Times are UTC by default -- that's the zone ADS-B Exchange, ATC and
    pilots already use, and the one zone that can't be silently wrong for a
    reporter who isn't in any particular city. Local time is opt-in:

    - None / "" / "utc"  -> None (stay in UTC, no local column added)
    - a named IANA zone   -> that zone, e.g. "America/Los_Angeles"
    - "auto"              -> inferred from a lat/lon (e.g. the trace's first
                              point), via timezonefinder, for when you want
                              local time but don't know or want to type the
                              zone for wherever this happened
    """
    if not timezone or timezone.lower() == "utc":
        return None

    if timezone.lower() == "auto":
        if lat is None or lon is None:
            raise ValueError("'auto' requires a lat/lon to infer a timezone from.")
        try:
            TimezoneFinder = _import_timezone_finder()
        except ImportError as exc:
            raise ImportError(
                "--timezone auto requires the 'timezonefinder' package.\n"
                "Install it with:\n"
                "    pip install timezonefinder\n"
                "or install flight-tracer with the tz extra:\n"
                "    pip install flight-tracer[tz]"
            ) from exc

        zone = TimezoneFinder().timezone_at(lat=float(lat), lng=float(lon))
        if not zone:
            raise ValueError(f"Could not determine a timezone for ({lat}, {lon}).")
        return zone

    return timezone


def _import_timezone_finder():
    """Import TimezoneFinder without numba dumping a traceback on a stale scipy.

    timezonefinder pulls in numba for its JIT-compiled point-in-polygon
    check. numba doesn't depend on scipy at all, but if *some* scipy happens
    to be installed (as it often is, transitively, in a shared environment)
    numba opportunistically tries to use it for BLAS acceleration -- and an
    older scipy built against NumPy 1.x's ABI crashes under NumPy 2.x with a
    raw `AttributeError: _ARRAY_API not found` traceback. It's caught
    internally and execution continues correctly either way, but it prints
    like a real failure. Disabling numba's JIT (only if the caller hasn't
    already set an opinion) skips that code path entirely; timezonefinder's
    lookup works the same, just interpreted rather than compiled -- plenty
    fast for one point-in-polygon check per run.
    """
    import os
    import warnings

    os.environ.setdefault("NUMBA_DISABLE_JIT", "1")
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, module="numba")
        from timezonefinder import TimezoneFinder
    return TimezoneFinder
