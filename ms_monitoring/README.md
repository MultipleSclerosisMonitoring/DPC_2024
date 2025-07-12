# ms_monitoring

Command-line tools for extracting and processing wearable activity data
in multiple sclerosis monitoring studies.

## High-Level Workflow

```mermaid
sequenceDiagram
    participant U as User
    participant C1 as find_mscodeids CLI
    participant P as CodeIDProcessor
    participant DM as DataManager
    participant DB as InfluxDB
    participant PG as PostgreSQL
    U->>C1: run `python -m ms_monitoring.find_mscodeids`
    C1->>P: __init__(config)
    P->>DM: get_codeids_in_range()
    DM->>DB: query distinct CodeIDs
    DM->>PG: INSERT activity_leg & activity_all
    P-->>C1: print INFO_ALL_PROCESSED
    C1-->>U: display summary

    %% spacer
    C1--x C2: 

    participant C2 as find_gait CLI
    participant M as MovementDetector

    U->>C2: run `python -m ms_monitoring.find_gait`
    C2->>M: __init__(ids, config)
    M->>DM: segments_retrieval(ids)
    DM->>PG: SELECT * FROM activity_all
    M->>DB: fetch_sensor_data()
    DB-->>M: raw DataFrame
    M->>DM: store effective_movement & gait
    DM->>PG: INSERT effective tables
    M-->>C2: return DataFrames
    C2-->>U: print summaries
```

## Requirements

- Python 3.12 or higher  
- A `config.yaml` in the project root defining your InfluxDB and PostgreSQL connections:

  ```yaml
  influxdb:
    url:      "https://<host>:8086"
    token:    "<YOUR_TOKEN>"
    org:      "<ORG>"
    bucket:   "<BUCKET>"
    measurement: "<MEASUREMENT>"
    verify:   false
    timeout:  900000

  postgresql:
    host:     "<PG_HOST>"
    port:     5432
    user:     "<USER>"
    password: "<PASSWORD>"
    database: "<DB_NAME>"
  ```

## Installation

```bash
# From the repository root:
pip install -r requirements.txt
```

## Usage

### 1. find_mscodeids

Extracts unique device CodeIDs, identifies activity segments (“Left” & “Right” foot),
and writes to PostgreSQL tables `activity_leg` and `activity_all`.

```bash
python -m ms_monitoring.find_mscodeids   -c config.yaml   [-f "YYYY-MM-DD HH:MM:SS"]   [-u "YYYY-MM-DD HH:MM:SS"]   [-l en]   [-v N]   [--head-rows M]
```

- `-c, --config`   Path to YAML config (required).
- `-f, --from`     Start datetime (default: yesterday at 00:00:00).
- `-u, --until`    End datetime (default: now).
- `-l, --lang`     Interface language (`en`, `es`; default: `en`).
- `-v, --verbose`  Verbosity level (0–3+).
- `--head-rows`    Rows to preview when `-v ≥ 2` (default: 5).

### 2. find_gait

Processes stored activity segments, applies power/time-based checks
to detect effective movements and gait, and optionally saves results.

```bash
python -m ms_monitoring.find_gait   -c config.yaml   -i "[ID1,ID2,...]"   [-l en]   [--output raw_data.xlsx]   [--head-rows N]   [--save]   [-v N]
```

- `-c, --config`   Path to YAML config (required).
- `-i, --ids`      JSON list of `activity_all` record IDs (required).
- `-l, --lang`     Interface language (`en`, `es`; default: `en`).
- `--output`       Optional XLSX export of raw sensor data.
- `--head-rows`    Rows to preview when `-v ≥ 2` (default: 5).
- `--save`         Persist results in tables `effective_movement` & `effective_gait`.
- `-v, --verbose`  Verbosity level (0–2).

## SQL Schema Extension

In addition to the standard tables (`codeids`, `activity_leg`, `activity_all`,
`effective_movement`), the following table is created to store gait episodes:

```sql
CREATE TABLE IF NOT EXISTS effective_gait (
  id          SERIAL PRIMARY KEY,
  codeid_id   INT REFERENCES codeids(id),
  start_time  TIMESTAMPTZ NOT NULL,
  end_time    TIMESTAMPTZ NOT NULL,
  duration    NUMERIC NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_effective_gait_codeid 
  ON effective_gait(codeid_id);
```

## License

This project is released under the **MIT License**. See the `LICENSE` file for details.
