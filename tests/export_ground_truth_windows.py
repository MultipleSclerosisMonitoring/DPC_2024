import argparse
from pathlib import Path

import pandas as pd
from pandas.api.types import DatetimeTZDtype, is_datetime64_any_dtype

from msTools.data_manager import DataManager
from msTools.timeutils import ensure_utc


FIELDS = ["Ax", "Ay", "Az", "Gx", "Gy", "Gz"]


def fetch_window_sensor_data(
    data_manager: DataManager,
    codeid: str,
    foot: str,
    start_time,
    end_time,
) -> pd.DataFrame:
    start_utc = ensure_utc(start_time).isoformat().replace("+00:00", "Z")
    end_utc = ensure_utc(end_time).isoformat().replace("+00:00", "Z")

    field_filter = " or ".join([f'r["_field"] == "{field}"' for field in FIELDS])

    query = f'''
    from(bucket: "{data_manager.bucket}")
        |> range(start: {start_utc}, stop: {end_utc})
        |> filter(fn: (r) => r["_measurement"] == "{data_manager.measurement}")
        |> filter(fn: (r) => r["CodeID"] == "{codeid}")
        |> filter(fn: (r) => r["Foot"] == "{foot}")
        |> filter(fn: (r) => {field_filter})
        |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
        |> keep(columns: ["_time", "CodeID", "Foot", "Ax", "Ay", "Az", "Gx", "Gy", "Gz"])
    '''

    try:
        result = data_manager.influxdb_client.query_api().query(
            query=query,
            org=data_manager.config["influxdb"]["org"]
        )
        rows = [record.values for table in result for record in table.records]
        df = pd.DataFrame(rows)

        if df.empty:
            return pd.DataFrame(columns=["_time", "CodeID", "Foot"] + FIELDS)

        df["_time"] = pd.to_datetime(df["_time"], errors="coerce")
        df = df.dropna(subset=["_time"]).sort_values("_time").reset_index(drop=True)

        return df

    except Exception as e:
        print(f"Error fetching data for CodeID={codeid}, foot={foot}, range=({start_time}, {end_time}): {e}")
        return pd.DataFrame(columns=["_time", "CodeID", "Foot"] + FIELDS)


def make_excel_safe(df: pd.DataFrame) -> pd.DataFrame:
    safe = df.copy()

    for col in safe.columns:
        series = safe[col]

        if isinstance(series.dtype, DatetimeTZDtype):
            safe[col] = series.dt.tz_convert("Europe/Madrid").dt.tz_localize(None)
        elif is_datetime64_any_dtype(series):
            continue

    return safe


def truncate_sheet_name(name: str, max_len: int = 31) -> str:
    return name[:max_len]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export raw signal windows for manual ground-truth annotation."
    )
    parser.add_argument(
        "-c", "--config",
        required=True,
        help="Path to config.yaml"
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to ground_truth_template.xlsx"
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        help="Output XLSX with raw windows"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit of samples to export"
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    template = pd.read_excel(input_path, sheet_name="ground_truth")
    if args.limit is not None:
        template = template.head(args.limit).copy()

    required_cols = {
        "sample_id", "CodeID", "from", "until"
    }
    missing = required_cols - set(template.columns)
    if missing:
        raise ValueError(f"Missing required columns in template: {missing}")

    template["from"] = pd.to_datetime(template["from"], errors="coerce")
    template["until"] = pd.to_datetime(template["until"], errors="coerce")
    template = template.dropna(subset=["from", "until", "CodeID"]).copy()

    dm = DataManager(config_path=args.config)

    try:
        summary_rows = []

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            make_excel_safe(template).to_excel(writer, sheet_name="ground_truth", index=False)

            for _, row in template.iterrows():
                sample_id = int(row["sample_id"])
                codeid = str(row["CodeID"])
                start_time = row["from"]
                end_time = row["until"]

                left_df = fetch_window_sensor_data(dm, codeid, "Left", start_time, end_time)
                right_df = fetch_window_sensor_data(dm, codeid, "Right", start_time, end_time)

                left_count = len(left_df)
                right_count = len(right_df)

                summary_rows.append({
                    "sample_id": sample_id,
                    "CodeID": codeid,
                    "from": start_time,
                    "until": end_time,
                    "left_rows": left_count,
                    "right_rows": right_count,
                    "left_has_data": left_count > 0,
                    "right_has_data": right_count > 0,
                })

                if not left_df.empty:
                    make_excel_safe(left_df).to_excel(
                        writer,
                        sheet_name=truncate_sheet_name(f"S{sample_id}_L"),
                        index=False
                    )

                if not right_df.empty:
                    make_excel_safe(right_df).to_excel(
                        writer,
                        sheet_name=truncate_sheet_name(f"S{sample_id}_R"),
                        index=False
                    )

            summary_df = pd.DataFrame(summary_rows)
            make_excel_safe(summary_df).to_excel(writer, sheet_name="summary", index=False)

        print(f"Raw windows exported to: {output_path}")
        print(f"Samples exported: {len(template)}")

    finally:
        dm.close_all()


if __name__ == "__main__":
    main()