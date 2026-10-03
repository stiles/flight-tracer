"""Explicit, inclusive time windows, normalized to UTC."""

import re
import pandas as pd
import pytz


def parse_window(after=None, before=None, timezone="UTC"):
    zone = pytz.timezone(timezone)

    def parse(value):
        if value is None:
            return None
        # Require a full date to avoid guessing a day for an overnight flight.
        if not re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", value):
            raise ValueError("Window bounds require a full date and time, e.g. 2020-01-26T09:00:00")
        stamp = pd.Timestamp(value)
        if stamp.tzinfo is None:
            stamp = stamp.tz_localize(zone, ambiguous="raise", nonexistent="raise")
        return stamp.tz_convert("UTC")

    start, end = parse(after), parse(before)
    if start is not None and end is not None and start > end:
        raise ValueError("--after must be at or before --before")
    return start, end


def select_window(df, start=None, end=None):
    mask = pd.Series(True, index=df.index)
    if start is not None:
        mask &= df["point_time_utc"] >= start
    if end is not None:
        mask &= df["point_time_utc"] <= end
    return df.loc[mask].copy().reset_index(drop=True)
