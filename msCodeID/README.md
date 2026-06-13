# msCodeID

The **msCodeID** package implements the first semantic stage of the repository.

Its role is to retrieve wearable references from InfluxDB, identify contiguous
activity segments for each foot, and prepare the bilateral semantic structures
that are later stored in PostgreSQL as `activity_leg` and `activity_all`.

## Responsibilities

The package centers on the `CodeIDProcessor` class, which is responsible for:

- retrieving CodeID-level wearable reference data from InfluxDB
- identifying contiguous activity segments for the left and right foot
- building per-leg semantic frames compatible with `activity_leg`
- computing bilateral temporal overlaps between both legs
- building bilateral semantic frames compatible with `activity_all`

This means `msCodeID` is the module that performs the **bottom-up semantic
construction** required before the gait-detection stage begins.

## Core Component

### `CodeIDProcessor` (`codeid_processor.py`)

Main public methods include:

- `__init__(data_manager: DataManager, verbose: int = 0) -> None`
- `fetch_codeid_data(codeid: str, start_datetime: datetime, end_datetime: datetime) -> pandas.DataFrame`
- `identify_activity_segments(df: pandas.DataFrame, threshold_seconds: float = 70, foot: str = "Left") -> pandas.DataFrame`
- `build_activity_leg_frames(sensor_data: pandas.DataFrame, codeid_id: int, gap_threshold_seconds: float = 80.0) -> tuple[pandas.DataFrame, pandas.DataFrame, pandas.DataFrame, pandas.DataFrame]`
- `build_activity_all_frame(activity_seg_right_merge: pandas.DataFrame, activity_seg_left_merge: pandas.DataFrame) -> pandas.DataFrame`
- `inter_segs(sg1: pandas.DataFrame, sg2: pandas.DataFrame) -> pandas.DataFrame`
- `merge_activity_legs_to_all(act_segR: pandas.DataFrame, act_segL: pandas.DataFrame, inter: pandas.DataFrame) -> pandas.DataFrame`
- `save_to_postgresql(table_name: str, df: pandas.DataFrame) -> None`

## How it fits into the pipeline

The repository workflow is divided into two main stages:

### Stage 1: semantic construction

Handled by `msCodeID` and the CLI script `find_mscodeids`.

Flow:

1. retrieve distinct `CodeID` values from InfluxDB
2. fetch wearable reference data for each `CodeID`
3. split the stream by foot (`Left` / `Right`)
4. build contiguous per-leg activity segments
5. store those segments as `activity_leg`
6. compute bilateral overlaps
7. store those overlaps as `activity_all`

### Stage 2: movement and gait detection

Handled later by `msGait` and `find_gait`.

That second stage reads the previously built `activity_all` rows and derives:

- `effective_movement`
- `effective_gait`
- GPS-enriched gait metrics

## Configuration

`msCodeID` relies on the shared project-level `config.yaml`, with optional local secret overrides loaded from `.env`.

Relevant sections include:

```yaml
influxdb:
  url: "https://<HOST>:8086"
  token: "<YOUR_TOKEN>"
  org: "<ORG>"
  bucket: "<BUCKET>"
  measurement: "<MEASUREMENT>"
  verify: false
  timeout: 900000

postgresql:
  host: "<PG_HOST>"
  port: 5432
  user: "<USER>"
  password: "<PASSWORD>"
  database: "<DB_NAME>"
```

## Usage in Python

```python
from msTools.data_manager import DataManager
from msCodeID.codeid_processor import CodeIDProcessor

manager = DataManager(config_path="config.yaml")
processor = CodeIDProcessor(manager, verbose=1)

df = processor.fetch_codeid_data(
    codeid="JB20250511-47",
    start_datetime="2025-05-11 00:00:00",
    end_datetime="2025-05-12 00:00:00",
)

print(df.head())

manager.close_all()
```

## CLI Integration

Although **msCodeID** does not expose its own standalone CLI, it is used directly
by the `find_mscodeids` command:

```bash
python -m ms_monitoring.find_mscodeids \
  -c config.yaml \
  -f "2025-05-11 00:00:00" \
  -u "2025-05-12 00:00:00" \
  --save 1 \
  -v 2
```

This command may generate:

- rows in `codeids`
- rows in `activity_leg`
- rows in `activity_all`

## Notes

- timestamps are normalized through the shared `ensure_utc(...)` utility
- activity segmentation is gap-based
- zero-duration segments are filtered out
- bilateral activity is built through temporal intersection of left and right legs
- this package depends on `msTools` for database access and shared infrastructure

## Requirements

- Python 3.11
- project dependencies installed through `poetry install` or `pip install -r requirements.txt`

## License

MIT License. See the root `LICENSE` file for details.
