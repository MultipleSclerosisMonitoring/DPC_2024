# msTools

Shared utility package for the MS Monitoring project.

`msTools` provides the infrastructure used by the rest of the repository:
configuration loading, time normalization, internationalization, shared
Pydantic models, and database access for both InfluxDB and PostgreSQL.

## Responsibilities

The package centers on `DataManager`, which is responsible for:

- loading `config.yaml`
- creating and closing PostgreSQL and InfluxDB connections
- retrieving CodeIDs from InfluxDB
- retrieving `activity_all` windows from PostgreSQL
- expanding bilateral windows into leg-level rows
- validating and storing semantic tables with idempotent inserts
- updating GPS-related fields in `effective_gait` when required

It also includes:

- `settings.py` for typed configuration loading and `.env` overrides
- `models.py` for shared Pydantic models
- `timeutils.py` for UTC normalization
- `i18n.py` for gettext-based translations

## Main Components

### `DataManager` (`data_manager.py`)

Main methods include:

- `__init__(config_path: str) -> None`
- `load_config(config_path: str) -> dict[str, Any]`
- `get_config(sect: str) -> dict[str, Any] | None`
- `get_influx_client() -> InfluxDBClient`
- `get_codeids_in_range(start_datetime: str, end_datetime: str) -> list[str]`
- `fetch_data(query: str) -> pandas.DataFrame`
- `segments_retrieval(fstart: str | None = None, fend: str | None = None, ids: list[int] | None = None, verbose: int = 0) -> pandas.DataFrame`
- `recover_activity_all(act: pandas.DataFrame, verbose: int = 0) -> pandas.DataFrame`
- `store_codeid(codeid: str, verbose: int = 0) -> tuple[int, bool]`
- `transform_activityleg(data: pandas.DataFrame) -> pandas.DataFrame`
- `store_data(table_name: str, data: pandas.DataFrame, verbose: int = 1) -> list[int]`
- `get_real_codeid(codeid_id: int) -> str`
- `get_codeid_id_by_value(codeid: str) -> int | None`
- `get_record_all_legs(clegs: set, clname: str = "codeleg_ids") -> pandas.DataFrame`
- `get_activity_ids_by_start_date_range(start_datetime: str | datetime, end_datetime: str | datetime) -> list[int]`
- `close_pg() -> None`
- `close_influxdb() -> None`
- `close_all() -> None`

### `models.py`

Shared Pydantic models used before writing data to PostgreSQL:

- `CodeID`
- `ActivityLeg`
- `ActivityAll`

### `timeutils.py`

Contains:

- `ensure_utc(ts: str | pandas.Timestamp | datetime) -> pandas.Timestamp`

This helper converts local or timezone-aware timestamps into UTC-aware pandas
timestamps, which is essential for keeping PostgreSQL and InfluxDB queries
consistent.

### `i18n.py`

Provides lightweight internationalization helpers:

- `detect_language(...)`
- `available_languages(...)`
- `init_translation(...)`
- `set_locale_for_formatting(...)`
- `gettext(...)`

## How `msTools` fits into the pipeline

`msTools` supports both major stages of the repository workflow:

### Stage 1: bottom-up semantic construction

- raw wearable data is queried from InfluxDB
- `activity_leg` is built per foot
- bilateral overlaps are merged into `activity_all`

### Stage 2: movement and gait detection

- `activity_all` windows are read back from PostgreSQL
- bilateral windows are expanded into per-leg rows
- downstream modules derive `effective_movement`
- bilateral gait events are stored in `effective_gait`
- `effective_gait` may be enriched with GPS metrics

## Configuration

The package reads configuration from `config.yaml`, with optional overrides from a local `.env` file. The repository includes `.env.example` as a documented template.

Example:

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

## Usage example

```python
from msTools.data_manager import DataManager

manager = DataManager(config_path="config.yaml")

codeids = manager.get_codeids_in_range(
    "2025-05-11 00:00:00",
    "2025-05-12 00:00:00",
)
print(codeids)

manager.close_all()
```

## Notes

- semantic timestamps are handled with timezone awareness
- PostgreSQL inserts are validated with Pydantic models
- the storage logic is designed to be idempotent for the main semantic tables
- `effective_gait` may include GPS enrichment fields such as distance, elapsed time, average speed, and validation flag

## Documentation

Full Sphinx documentation is available in `docs/`.

```bash
cd docs
make html
```

## Requirements

- Python 3.11
- project dependencies installed through `poetry install` or `pip install -r requirements.txt`

## License

MIT License. See the root `LICENSE` file for details.
