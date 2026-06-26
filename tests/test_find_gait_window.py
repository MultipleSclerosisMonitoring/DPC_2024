from datetime import datetime, timezone

from ms_monitoring.find_gait import _resolve_time_window


def test_resolve_time_window_prefers_explicit_range() -> None:
    now = datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)

    fstart, fend = _resolve_time_window(
        from_date="2024-01-02T10:00:00",
        until_date="2024-01-02T11:00:00",
        hours_back=25,
        now=now,
    )

    assert fstart == "2024-01-02T10:00:00Z"
    assert fend == "2024-01-02T11:00:00Z"


def test_resolve_time_window_falls_back_to_last_hours() -> None:
    now = datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)

    fstart, fend = _resolve_time_window(
        from_date=None,
        until_date=None,
        hours_back=3,
        now=now,
    )

    assert fstart == "2024-01-02T09:00:00Z"
    assert fend == "2024-01-02T12:00:00Z"
