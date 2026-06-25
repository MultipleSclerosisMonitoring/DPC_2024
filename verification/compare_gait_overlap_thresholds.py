from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from msGait.movement_detector import MovementDetector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare gait coverage for two min_gait_duration thresholds."
    )
    parser.add_argument(
        "--excel",
        required=True,
        help="Path to the Excel file containing the coverage sheet.",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to the repository config file.",
    )
    parser.add_argument(
        "--sheet",
        default="coverage",
        help="Excel sheet name to read.",
    )
    parser.add_argument(
        "--threshold-a",
        type=float,
        default=6.0,
        help="Baseline min_gait_duration_sec threshold.",
    )
    parser.add_argument(
        "--threshold-b",
        type=float,
        default=3.0,
        help="Candidate min_gait_duration_sec threshold.",
    )
    parser.add_argument(
        "--output-dir",
        default="verification/out/gait_threshold_compare",
        help="Directory where CSV outputs will be written.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on number of events for faster dry runs.",
    )
    return parser.parse_args()


def load_event_grid(excel_path: str, sheet_name: str) -> pd.DataFrame:
    coverage = pd.read_excel(excel_path, sheet_name=sheet_name)
    key = ["code_id", "test_name", "event_started_at", "event_ended_at"]
    events = coverage[key].drop_duplicates().copy()

    status_grid = (
        coverage.pivot_table(
            index=key,
            columns="source",
            values="status",
            aggfunc="first",
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )

    events = events.merge(
        status_grid,
        on=key,
        how="left",
    )
    return events


def build_windows(codeid_id: int, code_id: str, started_at, ended_at) -> pd.DataFrame:
    start_utc = pd.Timestamp(started_at).tz_localize("Europe/Madrid").tz_convert("UTC")
    end_utc = pd.Timestamp(ended_at).tz_localize("Europe/Madrid").tz_convert("UTC")
    return pd.DataFrame(
        [
            {
                "codeid_id": codeid_id,
                "CodeID": code_id,
                "foot": "Left",
                "start_time": start_utc,
                "end_time": end_utc,
            },
            {
                "codeid_id": codeid_id,
                "CodeID": code_id,
                "foot": "Right",
                "start_time": start_utc,
                "end_time": end_utc,
            },
        ]
    )


def run_threshold_analysis(
    detector: MovementDetector,
    windows: pd.DataFrame,
    threshold: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df_effective = detector.detect_effective_movement(windows, None, 0)
    detector.min_gait_duration_sec = threshold
    df_gait = detector.detect_effective_gait(df_effective, 0)
    df_gait = detector.validate_gait_with_gps(df_gait, 0)
    return df_effective, df_gait


def summarize(details: pd.DataFrame, threshold_a: float, threshold_b: float) -> pd.DataFrame:
    gait_a_col = f"gait_rows_{int(threshold_a)}s"
    gait_b_col = f"gait_rows_{int(threshold_b)}s"

    work = details.copy()
    work["has_codeid"] = ~work["codeid_missing"]
    work["has_effective_movement"] = work["effective_rows"] > 0
    work[f"has_gait_{int(threshold_a)}s"] = work[gait_a_col] > 0
    work[f"has_gait_{int(threshold_b)}s"] = work[gait_b_col] > 0
    work["new_gait_events"] = (work[gait_a_col] == 0) & (work[gait_b_col] > 0)
    work["new_from_coverage_none"] = work["new_gait_events"] & work["effective_gait"].eq("none")

    rows: list[dict[str, object]] = []
    for test_name, group in work.groupby("test_name", dropna=False):
        rows.append(
            {
                "test_name": test_name,
                "events": len(group),
                "codeid_missing": int(group["codeid_missing"].sum()),
                "effective_zero": int((group["effective_rows"] == 0).sum()),
                f"gait_events_{int(threshold_a)}s": int((group[gait_a_col] > 0).sum()),
                f"gait_events_{int(threshold_b)}s": int((group[gait_b_col] > 0).sum()),
                "new_gait_events": int(group["new_gait_events"].sum()),
                "new_from_coverage_none": int(group["new_from_coverage_none"].sum()),
            }
        )

    total = pd.DataFrame(
        [
            {
                "test_name": "TOTAL",
                "events": len(work),
                "codeid_missing": int(work["codeid_missing"].sum()),
                "effective_zero": int((work["effective_rows"] == 0).sum()),
                f"gait_events_{int(threshold_a)}s": int((work[gait_a_col] > 0).sum()),
                f"gait_events_{int(threshold_b)}s": int((work[gait_b_col] > 0).sum()),
                "new_gait_events": int(work["new_gait_events"].sum()),
                "new_from_coverage_none": int(work["new_from_coverage_none"].sum()),
            }
        ]
    )
    return pd.concat([pd.DataFrame(rows), total], ignore_index=True)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    events = load_event_grid(args.excel, args.sheet)
    if args.limit is not None:
        events = events.head(args.limit).copy()

    detector = MovementDetector(config_file=args.config, ids=[], verbose=0)
    try:
        detail_rows: list[dict[str, object]] = []
        for row in events.itertuples(index=False):
            code_id = str(row.code_id)
            codeid_id = detector.data_manager.get_codeid_id_by_value(code_id)
            base = {
                "code_id": code_id,
                "test_name": row.test_name,
                "event_started_at": row.event_started_at,
                "event_ended_at": row.event_ended_at,
                "event_duration_s": (
                    pd.Timestamp(row.event_ended_at) - pd.Timestamp(row.event_started_at)
                ).total_seconds(),
                "activity_all": getattr(row, "activity_all", None),
                "activity_leg": getattr(row, "activity_leg", None),
                "effective_movement": getattr(row, "effective_movement", None),
                "effective_gait": getattr(row, "effective_gait", None),
                "codeid_missing": codeid_id is None,
            }

            if codeid_id is None:
                detail_rows.append(
                    base
                    | {
                        "effective_rows": pd.NA,
                        "effective_total_s": pd.NA,
                        f"gait_rows_{int(args.threshold_a)}s": pd.NA,
                        f"gait_total_s_{int(args.threshold_a)}s": pd.NA,
                        f"gps_validated_rows_{int(args.threshold_a)}s": pd.NA,
                        f"gait_rows_{int(args.threshold_b)}s": pd.NA,
                        f"gait_total_s_{int(args.threshold_b)}s": pd.NA,
                        f"gps_validated_rows_{int(args.threshold_b)}s": pd.NA,
                    }
                )
                continue

            windows = build_windows(
                codeid_id=codeid_id,
                code_id=code_id,
                started_at=row.event_started_at,
                ended_at=row.event_ended_at,
            )

            df_effective, df_gait_a = run_threshold_analysis(
                detector=detector,
                windows=windows,
                threshold=args.threshold_a,
            )
            _, df_gait_b = run_threshold_analysis(
                detector=detector,
                windows=windows,
                threshold=args.threshold_b,
            )

            detail_rows.append(
                base
                | {
                    "effective_rows": len(df_effective),
                    "effective_total_s": float(df_effective["duration"].sum()) if not df_effective.empty else 0.0,
                    f"gait_rows_{int(args.threshold_a)}s": len(df_gait_a),
                    f"gait_total_s_{int(args.threshold_a)}s": float(df_gait_a["duration"].sum()) if not df_gait_a.empty else 0.0,
                    f"gps_validated_rows_{int(args.threshold_a)}s": int(df_gait_a["gps_validated"].fillna(False).sum()) if not df_gait_a.empty else 0,
                    f"gait_rows_{int(args.threshold_b)}s": len(df_gait_b),
                    f"gait_total_s_{int(args.threshold_b)}s": float(df_gait_b["duration"].sum()) if not df_gait_b.empty else 0.0,
                    f"gps_validated_rows_{int(args.threshold_b)}s": int(df_gait_b["gps_validated"].fillna(False).sum()) if not df_gait_b.empty else 0,
                }
            )

        details = pd.DataFrame(detail_rows)
        summary = summarize(details, args.threshold_a, args.threshold_b)

        details_path = output_dir / "details.csv"
        summary_path = output_dir / "summary.csv"
        details.to_csv(details_path, index=False)
        summary.to_csv(summary_path, index=False)

        print(f"details_csv={details_path}")
        print(f"summary_csv={summary_path}")
        print(summary.to_string(index=False))
    finally:
        detector.close()


if __name__ == "__main__":
    main()
