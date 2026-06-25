[![Build Status](https://img.shields.io/github/actions/workflow/status/MultipleSclerosisMonitoring/DPC_2024/ci.yml?branch=main)](https://github.com/MultipleSclerosisMonitoring/DPC_2024/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

# MS Monitoring

Modular Python utilities for transforming raw wearable-device telemetry into
semantic activity windows, movement detections, and graded bilateral gait
signals for multiple sclerosis monitoring studies.

## Why this repository exists

The project is built around a blind processing pipeline. It does not classify
clinical tests directly from the start. Instead, it progressively turns raw
telemetry into more interpretable semantic layers that can later be checked
against known clinical protocols. In that sense, the repository should be read
as a semantic digital health pipeline rather than as a standalone validated
clinical gait instrument.

Those layers are:

- `codeids`
- `activity_leg`
- `activity_all`
- `effective_movement`
- `effective_gait`
- optional clinical-test intervals aligned later as annotations

`codeids` can also act as a lightweight operational inventory when it contains
optional metadata fields such as `type`, `bucket`, `first_seen_at`, and
`last_seen_at`.

When the optional timestamp columns are present, `find_mscodeids` keeps them
up to date by applying minimum/maximum semantics to the observed raw-data
window for each CodeID.

`effective_gait` now exposes a unified confidence model:

- `gait_confidence_level = 1`: brief bilateral gait
- `gait_confidence_level = 2`: robust bilateral gait

That extension is important for post-hoc compatibility analysis, especially for
short clinical tests such as TUG and T25FW.

## End-to-end view

```mermaid
flowchart LR
    A[Raw telemetry in InfluxDB] --> B[find_mscodeids]
    B --> C[activity_leg]
    C --> D[activity_all]
    D --> E[find_gait]
    E --> F[effective_movement]
    F --> G[effective_gait\nbrief or robust]
    G --> H[Post-hoc clinical compatibility checks]
```

## Repository structure

```text
.
├── docs/                  Sphinx documentation
├── msTools/               Shared infrastructure and database access
├── msCodeID/              Bottom-up semantic construction
├── msGait/                Inertial movement and gait detection
├── ms_monitoring/         CLI entry points for both stages
├── tests/                 Ground-truth validation utilities
├── verification/          Threshold studies and compatibility reports
├── static/                Legacy figures and generated diagrams
├── requirements.txt       Pip dependencies
├── pyproject.toml         Poetry project definition
└── README.md              This file
```

## Functional architecture

### Stage 1: bottom-up semantic construction

The first stage discovers participants in a time range and creates semantic
candidate windows from raw wearable references.

Outputs:

- `codeids`
- `activity_leg`
- `activity_all`

### Stage 2: movement and graded gait detection

The second stage reuses `activity_all` as input, fetches inertial and GPS data,
detects per-leg movement, derives bilateral gait, and enriches the result.

Outputs:

- `effective_movement`
- `effective_gait`
- optional clinical-test intervals aligned later as annotations
- `gps_*` enrichment fields
- `gait_confidence_level`

## Package responsibilities

- `msTools`: shared configuration, time normalization, i18n, models, and DB access
- `msCodeID`: bottom-up semantic segmentation from raw reference streams
- `msGait`: inertial movement detection and graded bilateral gait detection
- `ms_monitoring`: CLI orchestration for both executable stages
- `tests` and `verification`: validation, threshold studies, and post-hoc reports

## Configuration

The repository uses a hybrid configuration model:

- `config.yaml` stores structural project configuration and algorithm parameters
- `.env` can override local secrets and connection values
- environment variables override both when present

Example movement section:

```yaml
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
  min_effective_duration_sec: 3.0
  min_gait_duration_sec:      6.0
  gps_resample_seconds:       10
  gps_padding_seconds:        15
  gps_min_points:             2
  gps_min_distance_m:         3.0
  gps_min_speed_m_s:          0.2
  gps_max_speed_m_s:          3.0
```

## Typical execution order

```bash
python -m ms_monitoring.check_user_tokens_multi -c config.yaml -b "Gait/autogen,MbientLab/autogen,SmartBand/autogen" --lookback-minutes 15 -v 1

python -m ms_monitoring.find_mscodeids -c config.yaml -f "2025-05-11 00:00:00" -u "2025-05-12 00:00:00" --save 1

python -m ms_monitoring.find_gait -c config.yaml -i "152,153" --save 1
```

For scheduled daily execution on a closed operational window, prefer:

```bash
python -m ms_monitoring.run_daily_pipeline -c config.yaml --save 1 -v 1
```

## Documentation

- Sphinx entry point: `docs/index.rst`
- system architecture: `docs/architecture.rst`
- package/module overview: `docs/modules.rst`
- package READMEs: `msTools/README.md`, `msCodeID/README.md`, `msGait/README.md`, `ms_monitoring/README.md`

To build the Sphinx site locally:

```bash
cd docs
make html
```

## Validation and reporting

The repository includes:

- ground-truth validation in `tests/`
- threshold comparison studies in `verification/`
- post-hoc gait compatibility reports that distinguish `none`, `brief`, and `robust`

## License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.
