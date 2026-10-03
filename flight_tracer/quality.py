"""Plain-data answers to: how much can this trace be trusted?"""

import pandas as pd

DEFAULT_GAP_MINUTES = 5

METADATA_FIELDS = {
    "registration": "registration",
    "aircraft_type": "model",
    "description": "desc",
    "owner_op": "owner_op",
}


def _pct(count, total):
    return round(100 * count / total, 1) if total else 0.0


def data_quality(gdf, gap_minutes=DEFAULT_GAP_MINUTES):
    """Coverage, staleness, metadata and leg-boundary facts for a processed trace.

    Gaps use the map's rule: consecutive points within one aircraft and leg
    more than `gap_minutes` apart. Time between legs is never a gap. Points
    dropped by ground filtering can widen a gap, so read these as coverage
    of what was kept, not proof of what the aircraft did.
    """
    if gdf.empty:
        return {}

    times = pd.to_datetime(gdf["point_time_utc"], utc=True)
    keys = [key for key in ("icao", "leg_id") if key in gdf]
    groups = gdf.assign(_t=times).groupby(keys, dropna=False) if keys else [(None, gdf.assign(_t=times))]

    tracked = gap_total = longest = 0.0
    gaps = 0
    for _, group in groups:
        elapsed = group["_t"].sort_values().diff().dropna().dt.total_seconds()
        tracked += elapsed.sum()
        over = elapsed[elapsed > gap_minutes * 60]
        gaps += len(over)
        gap_total += over.sum()
        if not over.empty:
            longest = max(longest, over.max())

    total = len(gdf)
    stale = int(gdf["is_stale"].fillna(False).astype(bool).sum()) if "is_stale" in gdf else 0
    mlat = int(gdf["position_source"].astype(str).str.contains("mlat", case=False, na=False).sum()) \
        if "position_source" in gdf else 0

    missing = [name for name, column in METADATA_FIELDS.items()
               if column not in gdf or gdf[column].isna().all()]
    if "call_sign" not in gdf or gdf["call_sign"].isna().all() or (gdf["call_sign"] == "UNKNOWN").all():
        missing.append("call_sign")

    boundaries = {}
    if "leg_detection" in gdf and "icao" in gdf:
        boundaries = {str(icao): group["leg_detection"].iloc[0] for icao, group in gdf.groupby("icao")}

    return {
        "tracked_minutes": round(tracked / 60, 1),
        "gap_threshold_minutes": gap_minutes,
        "gap_count": gaps,
        "gap_minutes_total": round(gap_total / 60, 1),
        "longest_gap_minutes": round(longest / 60, 1),
        "coverage_pct": round(100 * (1 - gap_total / tracked), 1) if tracked else 100.0,
        "stale_positions": {"count": stale, "pct": _pct(stale, total)},
        "mlat_positions": {"count": mlat, "pct": _pct(mlat, total)},
        "missing_values": {col: int(gdf[col].isna().sum()) for col in ("altitude", "ground_speed") if col in gdf},
        "missing_metadata": missing,
        "leg_boundaries": boundaries,
    }


def quality_notes(quality):
    """Short lines for what a reader should know before trusting the trace."""
    if not quality:
        return []
    notes = []
    if quality["gap_count"]:
        notes.append(
            f"{quality['gap_count']} tracking gap{'s' if quality['gap_count'] != 1 else ''} over "
            f"{quality['gap_threshold_minutes']:g} min (longest {quality['longest_gap_minutes']:g} min; "
            f"{quality['coverage_pct']:g}% of tracked time covered)"
        )
    if quality["stale_positions"]["count"]:
        notes.append(f"{quality['stale_positions']['pct']:g}% of positions flagged stale")
    if quality["mlat_positions"]["count"]:
        notes.append(f"{quality['mlat_positions']['pct']:g}% of positions multilaterated")
    if quality["missing_metadata"]:
        notes.append("missing metadata: " + ", ".join(quality["missing_metadata"]))
    states = set(quality["leg_boundaries"].values())
    if "unmarked" in states:
        notes.append("leg boundaries unavailable (no archive flags)")
    if "inferred_ground_stop" in states:
        notes.append("leg boundaries inferred from ground reports (estimates)")
    return notes
