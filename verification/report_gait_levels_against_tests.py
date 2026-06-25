from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from msGait.movement_detector import MovementDetector


KEY_COLUMNS = ["code_id", "test_name", "event_started_at", "event_ended_at"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a posterior test-compatibility report distinguishing brief and robust gait."
    )
    parser.add_argument("--excel", required=True, help="Path to the Excel file containing the coverage sheet.")
    parser.add_argument("--config", default="config.yaml", help="Path to the repository config file.")
    parser.add_argument("--sheet", default="coverage", help="Excel sheet name to read.")
    parser.add_argument(
        "--output-dir",
        default="verification/out/gait_level_report",
        help="Directory where CSV outputs will be written.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional cap on number of events for faster dry runs.")
    return parser.parse_args()


def load_event_grid(excel_path: str, sheet_name: str) -> pd.DataFrame:
    coverage = pd.read_excel(excel_path, sheet_name=sheet_name)
    events = coverage[KEY_COLUMNS].drop_duplicates().copy()
    status_grid = (
        coverage.pivot_table(index=KEY_COLUMNS, columns="source", values="status", aggfunc="first")
        .reset_index()
        .rename_axis(None, axis=1)
    )
    return events.merge(status_grid, on=KEY_COLUMNS, how="left")


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


def classify_gait_event(df_gait: pd.DataFrame) -> tuple[str, int, int, int, float, float]:
    if df_gait.empty:
        return "none", 0, 0, 0, 0.0, 0.0

    levels = pd.to_numeric(df_gait["gait_confidence_level"], errors="coerce").fillna(0).astype(int)
    brief_rows = int((levels == 1).sum())
    robust_rows = int((levels == 2).sum())
    max_level = int(levels.max()) if not levels.empty else 0
    brief_duration = float(df_gait.loc[levels == 1, "duration"].sum()) if brief_rows else 0.0
    robust_duration = float(df_gait.loc[levels == 2, "duration"].sum()) if robust_rows else 0.0

    if robust_rows > 0:
        return "robust", max_level, brief_rows, robust_rows, brief_duration, robust_duration
    if brief_rows > 0:
        return "brief", max_level, brief_rows, robust_rows, brief_duration, robust_duration
    return "none", max_level, brief_rows, robust_rows, brief_duration, robust_duration


def summarize(details: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for test_name, group in details.groupby("test_name", dropna=False):
        rows.append(
            {
                "test_name": test_name,
                "events": len(group),
                "codeid_missing": int(group["codeid_missing"].sum()),
                "effective_movement_detected": int(group["effective_rows"].fillna(0).gt(0).sum()),
                "gait_none": int(group["gait_category"].eq("none").sum()),
                "gait_brief": int(group["gait_category"].eq("brief").sum()),
                "gait_robust": int(group["gait_category"].eq("robust").sum()),
                "brief_rows_total": int(group["brief_gait_rows"].fillna(0).sum()),
                "robust_rows_total": int(group["robust_gait_rows"].fillna(0).sum()),
                "coverage_effective_gait_none": int(group["effective_gait"].eq("none").sum()),
                "coverage_effective_gait_partial": int(group["effective_gait"].eq("partial").sum()),
                "coverage_effective_gait_full": int(group["effective_gait"].eq("full").sum()),
            }
        )

    total = pd.DataFrame(
        [
            {
                "test_name": "TOTAL",
                "events": len(details),
                "codeid_missing": int(details["codeid_missing"].sum()),
                "effective_movement_detected": int(details["effective_rows"].fillna(0).gt(0).sum()),
                "gait_none": int(details["gait_category"].eq("none").sum()),
                "gait_brief": int(details["gait_category"].eq("brief").sum()),
                "gait_robust": int(details["gait_category"].eq("robust").sum()),
                "brief_rows_total": int(details["brief_gait_rows"].fillna(0).sum()),
                "robust_rows_total": int(details["robust_gait_rows"].fillna(0).sum()),
                "coverage_effective_gait_none": int(details["effective_gait"].eq("none").sum()),
                "coverage_effective_gait_partial": int(details["effective_gait"].eq("partial").sum()),
                "coverage_effective_gait_full": int(details["effective_gait"].eq("full").sum()),
            }
        ]
    )
    return pd.concat([pd.DataFrame(rows), total], ignore_index=True)


def main() -> None:
    args = parse_args()
    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    events = load_event_grid(args.excel, args.sheet)
    if args.limit is not None:
        events = events.head(args.limit).copy()

    detector = MovementDetector(config_file=args.config, ids=[], verbose=0)
    try:
        detail_rows: list[dict[str, object]] = []
        total_events = len(events)
        for idx, row in enumerate(events.itertuples(index=False), start=1):
            code_id = str(row.code_id)
            codeid_id = detector.data_manager.get_codeid_id_by_value(code_id)
            base = {
                "code_id": code_id,
                "test_name": row.test_name,
                "event_started_at": row.event_started_at,
                "event_ended_at": row.event_ended_at,
                "event_duration_s": (pd.Timestamp(row.event_ended_at) - pd.Timestamp(row.event_started_at)).total_seconds(),
                "activity_all": getattr(row, "activity_all", None),
                "activity_leg": getattr(row, "activity_leg", None),
                "effective_movement": getattr(row, "effective_movement", None),
                "effective_gait": getattr(row, "effective_gait", None),
                "codeid_missing": codeid_id is None,
            }
            if codeid_id is None:
                detail_rows.append(base | {
                    "effective_rows": pd.NA,
                    "effective_total_s": pd.NA,
                    "gait_category": pd.NA,
                    "max_gait_confidence_level": pd.NA,
                    "brief_gait_rows": pd.NA,
                    "robust_gait_rows": pd.NA,
                    "brief_gait_duration_s": pd.NA,
                    "robust_gait_duration_s": pd.NA,
                    "gps_validated_brief_rows": pd.NA,
                    "gps_validated_robust_rows": pd.NA,
                })
                continue

            windows = build_windows(codeid_id, code_id, row.event_started_at, row.event_ended_at)
            df_effective = detector.detect_effective_movement(windows, None, 0)
            df_gait = detector.detect_effective_gait(df_effective, 0)
            df_gait = detector.validate_gait_with_gps(df_gait, 0)

            gait_category, max_level, brief_rows, robust_rows, brief_dur, robust_dur = classify_gait_event(df_gait)
            levels = pd.to_numeric(df_gait.get("gait_confidence_level"), errors="coerce").fillna(0).astype(int) if not df_gait.empty else pd.Series(dtype=int)
            gps_valid_brief = int(df_gait.loc[levels == 1, "gps_validated"].fillna(False).sum()) if not df_gait.empty and "gps_validated" in df_gait.columns else 0
            gps_valid_robust = int(df_gait.loc[levels == 2, "gps_validated"].fillna(False).sum()) if not df_gait.empty and "gps_validated" in df_gait.columns else 0

            detail_rows.append(base | {
                "effective_rows": len(df_effective),
                "effective_total_s": float(df_effective["duration"].sum()) if not df_effective.empty else 0.0,
                "gait_category": gait_category,
                "max_gait_confidence_level": max_level,
                "brief_gait_rows": brief_rows,
                "robust_gait_rows": robust_rows,
                "brief_gait_duration_s": brief_dur,
                "robust_gait_duration_s": robust_dur,
                "gps_validated_brief_rows": gps_valid_brief,
                "gps_validated_robust_rows": gps_valid_robust,
            })
            if idx % 25 == 0 or idx == total_events:
                print(f"processed={idx}/{total_events}", flush=True)

        details = pd.DataFrame(detail_rows)
        summary = summarize(details)
        details_path = outdir / 'details.csv'
        summary_path = outdir / 'summary.csv'
        details.to_csv(details_path, index=False)
        summary.to_csv(summary_path, index=False)
        print(f"details_csv={details_path}")
        print(f"summary_csv={summary_path}")
        print(summary.to_string(index=False))
    finally:
        detector.close()


if __name__ == '__main__':
    main()
