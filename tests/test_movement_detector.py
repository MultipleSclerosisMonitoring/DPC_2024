from __future__ import annotations

import pandas as pd

from msGait.movement_detector import MovementDetector


def test_prepare_gps_track_resamples_and_deduplicates() -> None:
    gps_raw = pd.DataFrame(
        {
            "_time": [
                "2026-01-01T10:00:00Z",
                "2026-01-01T10:00:00Z",
                "2026-01-01T10:00:08Z",
                "2026-01-01T10:00:18Z",
            ],
            "lat": [40.0, 40.0, 40.0001, 40.0002],
            "lng": [-3.0, -3.0, -3.0001, -3.0002],
        }
    )

    prepared = MovementDetector._prepare_gps_track(gps_raw, resample_seconds=10)

    assert list(prepared.columns) == ["_time", "lat", "lng"]
    assert len(prepared) == 2
    assert prepared["_time"].is_monotonic_increasing


def test_summarize_prepared_gps_track_returns_validation_metrics() -> None:
    gps_track = pd.DataFrame(
        {
            "_time": pd.to_datetime(
                [
                    "2026-01-01T10:00:00Z",
                    "2026-01-01T10:00:10Z",
                    "2026-01-01T10:00:20Z",
                ],
                utc=True,
            ),
            "lat": [40.0, 40.0001, 40.0002],
            "lng": [-3.0, -3.0001, -3.0002],
        }
    )

    summary = MovementDetector._summarize_prepared_gps_track(
        gps_track=gps_track,
        min_points=2,
        min_distance_m=1.0,
        min_speed_m_s=0.01,
        max_speed_m_s=10.0,
    )

    assert summary["gps_points"] == 3
    assert summary["gps_distance_m"] > 0
    assert summary["gps_elapsed_sec"] == 20.0
    assert summary["gps_validated"] is True
