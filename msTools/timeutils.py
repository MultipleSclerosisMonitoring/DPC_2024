import datetime as dt

import pandas as pd


def ensure_utc(ts: str | pd.Timestamp | dt.datetime) -> pd.Timestamp:
    """Convert a timestamp-like value to a UTC-aware pandas Timestamp.

    If the input is timezone-naive, it is assumed to be in Europe/Madrid
    before being converted to UTC. If the input already has timezone
    information, it is converted directly to UTC.

    Args:
        ts: Datetime-like value to normalize. Supported inputs include
            strings, ``pandas.Timestamp`` and ``datetime.datetime``.

    Returns:
        A timezone-aware ``pandas.Timestamp`` normalized to UTC.

    Raises:
        ValueError: If the timestamp becomes ambiguous or invalid during
            timezone localization (for example, around DST transitions).
    """
    ts = pd.to_datetime(ts)

    if ts.tzinfo is None:
        ts = ts.tz_localize(
            "Europe/Madrid",
            ambiguous="NaT",
            nonexistent="shift_forward",
        )
        if pd.isna(ts):
            raise ValueError(f"Ambiguous local timestamp during DST transition: {ts}")

    return ts.tz_convert("UTC")