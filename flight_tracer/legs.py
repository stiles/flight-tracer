"""Conservative, opt-in inference for archives without leg flags."""

from math import asin, cos, radians, sin, sqrt
import pandas as pd


def ground_stop_boundaries(group):
    """Split at a ground report following a >=5-minute, <=1 km ground stop.

    Both reports must explicitly say ground and be consecutive records. A gap
    between airborne reports, or a numeric altitude <=0, is not evidence here.
    Require an earlier airborne record to avoid inventing an initial leg.
    """
    previous = None
    airborne = False
    for index, row in group.iterrows():
        ground = row["altitude"] == "ground"
        if (ground and airborne and previous is not None and previous["altitude"] == "ground"
                and all(pd.notna(v) for v in (row["lat"], row["lon"], previous["lat"], previous["lon"]))):
            minutes = (row["point_time_utc"] - previous["point_time_utc"]).total_seconds() / 60
            lat1, lat2 = radians(previous["lat"]), radians(row["lat"])
            dlat = lat2 - lat1
            dlon = radians(row["lon"] - previous["lon"])
            a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
            km = 6371 * 2 * asin(min(1, sqrt(a)))
            if minutes >= 5 and km <= 1:
                yield index
                airborne = False
        if not ground:
            if pd.notna(pd.to_numeric(row["altitude"], errors="coerce")):
                airborne = True
        previous = row
