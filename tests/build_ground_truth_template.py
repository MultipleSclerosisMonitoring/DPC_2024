import argparse
from pandas.api.types import DatetimeTZDtype, is_datetime64_any_dtype

import numpy as np
import pandas as pd

from msTools.data_manager import DataManager


def fetch_candidate_segments(
    data_manager: DataManager,
    min_duration: float,
    max_duration: float,
) -> pd.DataFrame:
    """
    Load candidate bilateral activity segments from activity_all joined with codeids.
    """
    query = """
        SELECT
            a.id AS activity_all_id,
            a.start_time,
            a.end_time,
            a.duration,
            a.codeid_ids,
            a.codeleg_ids,
            a.active_legs,
            c.id AS codeid_id,
            c.codeid AS "CodeID"
        FROM activity_all a
        JOIN codeids c
          ON c.id = a.codeid_ids[1]
        WHERE a.duration >= %s
          AND a.duration <= %s
          AND array_length(a.codeid_ids, 1) >= 1
        ORDER BY c.codeid, a.start_time
    """

    with data_manager.pg_conn.cursor() as cursor:
        cursor.execute(query, (min_duration, max_duration))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        return df

    df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce")
    df["end_time"] = pd.to_datetime(df["end_time"], errors="coerce")
    df = df.dropna(subset=["start_time", "end_time", "CodeID"]).copy()

    return df


def select_segments(
    df: pd.DataFrame,
    per_codeid: int,
    max_codeids: int,
    seed: int,
) -> pd.DataFrame:
    """
    Select up to N codeids and up to M segments per codeid, reproducibly.
    """
    if df.empty:
        return df

    rng = np.random.default_rng(seed)

    codeids = sorted(df["CodeID"].dropna().unique().tolist())
    if len(codeids) > max_codeids:
        selected_codeids = sorted(rng.choice(codeids, size=max_codeids, replace=False).tolist())
    else:
        selected_codeids = codeids

    selected_parts: list[pd.DataFrame] = []

    for codeid in selected_codeids:
        group = df[df["CodeID"] == codeid].copy()
        if group.empty:
            continue

        if len(group) > per_codeid:
            idx = rng.choice(group.index.to_numpy(), size=per_codeid, replace=False)
            group = group.loc[idx].copy()

        group = group.sort_values("start_time").reset_index(drop=True)
        selected_parts.append(group)

    if not selected_parts:
        return pd.DataFrame(columns=df.columns)

    return pd.concat(selected_parts, ignore_index=True)


def build_windows_from_segment(
    row: pd.Series,
    window_seconds: int,
    windows_per_segment: int,
) -> list[dict]:
    """
    Build one or more fixed windows inside a segment for manual annotation.
    """
    segment_start = pd.Timestamp(row["start_time"])
    segment_end = pd.Timestamp(row["end_time"])
    segment_duration = float(row["duration"])

    available_seconds = max((segment_end - segment_start).total_seconds(), 0.0)
    if available_seconds <= 0:
        return []

    real_window_seconds = min(float(window_seconds), available_seconds)

    if available_seconds <= real_window_seconds or windows_per_segment <= 1:
        offsets = [0.0]
    else:
        max_offset = available_seconds - real_window_seconds
        offsets = np.linspace(0.0, max_offset, num=windows_per_segment).tolist()

    result = []
    for offset_sec in offsets:
        window_start = segment_start + pd.to_timedelta(offset_sec, unit="s")
        window_end = window_start + pd.to_timedelta(real_window_seconds, unit="s")

        result.append(
            {
                "activity_all_id": int(row["activity_all_id"]),
                "codeid_id": int(row["codeid_id"]),
                "CodeID": row["CodeID"],
                "segment_start": segment_start,
                "segment_end": segment_end,
                "segment_duration_sec": segment_duration,
                "from": window_start,
                "until": window_end,
                "window_duration_sec": real_window_seconds,
                "Gait": "",
                "ReviewerNotes": "",
            }
        )

    return result


def build_ground_truth_template(
    df_segments: pd.DataFrame,
    window_seconds: int,
    windows_per_segment: int,
) -> pd.DataFrame:
    """
    Expand selected segments into annotation windows.
    """
    rows: list[dict] = []

    for _, row in df_segments.iterrows():
        rows.extend(
            build_windows_from_segment(
                row=row,
                window_seconds=window_seconds,
                windows_per_segment=windows_per_segment,
            )
        )

    result = pd.DataFrame(rows)
    if result.empty:
        return result

    result = result.sort_values(["CodeID", "from"]).reset_index(drop=True)
    result.insert(0, "sample_id", range(1, len(result) + 1))

    return result


def convert_datetimes_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    """
    Excel does not support timezone-aware datetimes.

    Convert datetime columns to Europe/Madrid local time and remove timezone info
    so the validator can later read them as naive local timestamps.
    """
    export_df = df.copy()

    for col in export_df.columns:
        series = export_df[col]

        if isinstance(series.dtype, DatetimeTZDtype):
            export_df[col] = (
                series.dt.tz_convert("Europe/Madrid")
                .dt.tz_localize(None)
            )
        elif is_datetime64_any_dtype(series):
            # already naive, leave as-is
            continue

    return export_df


def build_instructions_sheet() -> pd.DataFrame:
    """
    Create a small help sheet for manual annotation.
    """
    return pd.DataFrame(
        [
            {
                "Field": "Gait",
                "Meaning": "Put Y if the window clearly contains gait/walking, N if it does not."
            },
            {
                "Field": "ReviewerNotes",
                "Meaning": "Optional comments about doubts, artifacts, pauses, turns, etc."
            },
            {
                "Field": "from / until",
                "Meaning": "Window boundaries to validate manually."
            },
            {
                "Field": "CodeID",
                "Meaning": "Participant/device identifier."
            },
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an Excel template for manual ground-truth annotation."
    )
    parser.add_argument("-c", "--config", required=True, help="Path to config.yaml")
    parser.add_argument("-o", "--output", required=True, help="Output XLSX path")
    parser.add_argument("--min-duration", type=float, default=60.0, help="Minimum activity_all duration in seconds")
    parser.add_argument("--max-duration", type=float, default=900.0, help="Maximum activity_all duration in seconds")
    parser.add_argument("--per-codeid", type=int, default=5, help="Maximum selected segments per CodeID")
    parser.add_argument("--max-codeids", type=int, default=20, help="Maximum number of CodeIDs")
    parser.add_argument("--window-seconds", type=int, default=30, help="Length of each annotation window in seconds")
    parser.add_argument("--windows-per-segment", type=int, default=2, help="How many windows to sample per segment")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")

    args = parser.parse_args()

    data_manager = DataManager(config_path=args.config)

    try:
        candidates = fetch_candidate_segments(
            data_manager=data_manager,
            min_duration=args.min_duration,
            max_duration=args.max_duration,
        )

        if candidates.empty:
            print("No candidate segments found with the provided filters.")
            return

        selected = select_segments(
            df=candidates,
            per_codeid=args.per_codeid,
            max_codeids=args.max_codeids,
            seed=args.seed,
        )

        if selected.empty:
            print("No segments were selected.")
            return

        result = build_ground_truth_template(
            df_segments=selected,
            window_seconds=args.window_seconds,
            windows_per_segment=args.windows_per_segment,
        )

        if result.empty:
            print("No windows were generated for the template.")
            return

        result_to_export = convert_datetimes_for_excel(result)
        instructions = build_instructions_sheet()

        with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
            result_to_export.to_excel(writer, sheet_name="ground_truth", index=False)
            instructions.to_excel(writer, sheet_name="instructions", index=False)

        print(f"Ground-truth template created: {args.output}")
        print(f"Rows generated: {len(result_to_export)}")
        print(f"Unique CodeIDs: {result_to_export['CodeID'].nunique()}")

    finally:
        data_manager.close_all()


if __name__ == "__main__":
    main()