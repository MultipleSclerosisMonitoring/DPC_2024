[← Project Home](../README.md)

# ms_monitoring

Command-line tools for the two executable stages of the repository:

1. bottom-up semantic construction from raw wearable references
2. movement and gait detection over previously stored semantic windows

## Available CLIs

- `find_mscodeids`: retrieves distinct `CodeID` values from InfluxDB, builds
  per-leg `activity_leg` rows, and merges bilateral overlaps into `activity_all`
- `find_gait`: reads `activity_all`, reconstructs leg-wise windows, detects
  `effective_movement`, derives bilateral `effective_gait`, and enriches gait
  rows with GPS-based metrics

## Repository workflow

The normal execution order is:

1. run `find_mscodeids`
2. verify that `activity_leg` and `activity_all` were generated correctly
3. run `find_gait`
4. inspect `effective_movement` and `effective_gait`
5. optionally validate the algorithm with the utilities in `tests/`

## Requirements

- Python 3.11
- the repository includes a template `config.yaml` file in the project root
- replace the `XXX` placeholders in that file with your real local connection values

The public repository ships with a sanitized `config.yaml` template covering
InfluxDB, PostgreSQL, and movement-detection settings.

Example:

```yaml
influxdb:
  org: 'XXX'
  bucket: 'XXX/autogen'
  measurement: 'XXX'
  url: "https://XXX"
  token: 'XXX'
  verify: false
  timeout: 900000

postgresql:
  host: "XXX"
  user: "XXX"
  password: "XXX"
  database: "XXX"
  port: 5432

movement:
  accel_threshold:            0.2
  gyro_threshold:             60
  accel_power_threshold:      0.125
  gyro_power_threshold:       1000
  freq_band_min:              0.4
  freq_band_max:              1.6
  min_continuous_hits:        3
  sampling_rate:              47.0
  resample_hz:                100.0
  window_size_samples:        256
  min_window_fraction:        0.5
  min_effective_duration_sec: 6.0
  min_gait_duration_sec:      6.0
  gps_resample_seconds:       10
  gps_padding_seconds:        15
  gps_min_points:             2
  gps_min_distance_m:         3.0
  gps_min_speed_m_s:          0.2
  gps_max_speed_m_s:          3.0
```

## Installation

From the repository root:

```bash
pip install -r requirements.txt
```

Or with Poetry:

```bash
poetry install
```

## CLI 1: `find_mscodeids`

`find_mscodeids` is the first executable stage of the pipeline.

Its role is to:

- retrieve distinct `CodeID` values from InfluxDB for a time range
- fetch wearable reference data for each `CodeID`
- build contiguous activity segments separately for the left and right foot
- store those rows as `activity_leg`
- compute bilateral temporal overlaps and store them as `activity_all`

### Usage

```bash
python -m ms_monitoring.find_mscodeids \
  -c config.yaml \
  -f "YYYY-MM-DD HH:MM:SS" \
  -u "YYYY-MM-DD HH:MM:SS" \
  [--save 0|1] \
  [-l es|en] \
  [-v N] \
  [--head-rows M]
```

### Main options

- `-c, --config`: path to `config.yaml` (required)
- `-f, --from`: start datetime. If omitted, defaults to yesterday at `00:00:00`
- `-u, --until`: end datetime. If omitted, defaults to the current time
- `-l, --lang`: interface language (`es` or `en`)
- `--save`: persist results into PostgreSQL (`1`, default) or run as dry-run (`0`)
- `-v, --verbose`: verbosity level
- `--head-rows`: number of preview rows when verbose output is enabled

### Stored outputs

- `codeids`
- `activity_leg`
- `activity_all`


## CLI 2: `find_gait`

`find_gait` is the second executable stage of the pipeline.

Its role is to:

- read candidate bilateral windows from `activity_all`
- reconstruct one row per leg
- fetch raw inertial data from InfluxDB
- resample the inertial signal before analysis
- detect per-leg `effective_movement`
- derive bilateral `effective_gait`
- enrich gait rows with GPS-based metrics
- optionally store the results in PostgreSQL

### Usage

```bash
# Option A: explicit activity_all IDs
python -m ms_monitoring.find_gait \
  -c config.yaml \
  -i "1,5,10-15" \
  [--output raw_data.xlsx] \
  [--save 0|1] \
  [-l es|en] \
  [-v N] \
  [--head-rows M]

# Option B: if -i/--ids is omitted, process the last N hours
python -m ms_monitoring.find_gait \
  -c config.yaml \
  [--hours-back N] \
  [--output raw_data.xlsx] \
  [--save 0|1] \
  [-l es|en] \
  [-v N] \
  [--head-rows M]
```

### Main options

- `-c, --config`: path to `config.yaml` (required)
- `-i, --ids`: range/list of `activity_all` IDs. Examples: `1-271`, `1,5,10-15`
- `--hours-back`: fallback window when `--ids` is omitted
- `-o, --output`: optional XLSX export of fetched raw inertial data
- `-l, --lang`: interface language (`es` or `en`)
- `--save`: persist results into PostgreSQL (`1`, default) or run as dry-run (`0`)
- `-v, --verbose`: verbosity level
- `--head-rows`: number of preview rows when verbose output is enabled

### Stored outputs

- `effective_movement`
- `effective_gait`

## PostgreSQL notes

`effective_gait` contains both inertial gait information and GPS enrichment fields:

- `codeid_id`
- `start_time`
- `end_time`
- `duration`
- `gps_points`
- `gps_distance_m`
- `gps_elapsed_sec`
- `gps_avg_speed_m_s`
- `gps_validated`

A fresh installation should use `msTools/create_tables.sql`, which already
includes these columns.

## Dry-run mode

Both CLIs support dry execution through `--save 0`.

This is useful when you want to:

- inspect intermediate outputs without modifying PostgreSQL
- debug a time range
- validate segmentation or gait detection behaviour before persistence

## Validation utilities

The repository includes empirical validation utilities in `tests/`, based on a ground-truth Excel file with manually labeled windows.

Example:

```bash
python -m tests.validate_ground_truth \
  -e path/to/ground_truth.xlsx \
  -c config.yaml \
  -l es
```

This validation reports metrics such as:

- accuracy
- precision
- recall / sensitivity
- specificity
- F1-score
- Cohen's Kappa
- confusion matrix

## License

This project is released under the **MIT License**. See the root `LICENSE` file for details.
