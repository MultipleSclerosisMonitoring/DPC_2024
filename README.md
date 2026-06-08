[![Build Status](https://img.shields.io/github/actions/workflow/status/MultipleSclerosisMonitoring/DPC_2024/ci.yml?branch=main)](https://github.com/MultipleSclerosisMonitoring/DPC_2024/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

# MS Monitoring

Modular Python utilities for processing wearable-device data in multiple
sclerosis monitoring studies.

The repository is organized around a two-stage pipeline:

1. bottom-up semantic construction from raw wearable references
2. movement and gait detection over previously stored semantic windows

---

## Table of Contents

1. [High-Level Workflow](#high-level-workflow)
2. [Directory Structure](#directory-structure)
3. [Requirements](#requirements)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Validation](#validation)
7. [Documentation](#documentation)
8. [Contributing](#contributing)
9. [License](#license)

---

## High-Level Workflow

### 1. `find_mscodeids`

Extracts distinct device `CodeID` values from InfluxDB, builds `activity_leg`
(bottom-up per foot), and merges bilateral temporal overlaps into `activity_all`
for PostgreSQL persistence.

### 2. `find_gait`

Processes stored `activity_all` windows, retrieves raw inertial signals,
resamples them to a fixed frequency, applies spectral and temporal checks to
detect `effective_movement`, derives bilateral `effective_gait`, and enriches
gait episodes with GPS-based metrics.

## Directory Structure

```text
.
├── requirements.txt       # Pip dependencies
├── pyproject.toml         # Poetry project definition
├── docs/                  # Sphinx documentation
├── static/                # Reference figures and legacy diagrams
├── msTools/               # Shared utilities package
├── msCodeID/              # CodeID extraction and activity segmentation
├── msGait/                # Movement and gait detection
├── ms_monitoring/         # CLI entry-point scripts
├── tests/                 # Ground-truth validation utilities
└── README.md              # This file
```

## Requirements

- Python 3.11
- PostgreSQL
- InfluxDB
- the repository includes a template `config.yaml` file that must be edited locally with your real connection values

## Installation

### With Poetry

```bash
curl -sSL https://install.python-poetry.org | python3 -
git clone https://github.com/MultipleSclerosisMonitoring/DPC_2024.git
cd DPC_2024
poetry install
poetry shell
```

### With pip

```bash
python -m venv venv
source venv/bin/activate          # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

The repository includes a template `config.yaml` in the project root.

Replace the `XXX` placeholders with your real local connection values:

```yaml
influxdb:
  url:         "https://<HOST>:8086"
  token:       "<YOUR_TOKEN>"
  org:         "<ORG>"
  bucket:      "<BUCKET>"
  measurement: "<MEASUREMENT>"
  verify:      false
  timeout:     900000

postgresql:
  host:        "<PG_HOST>"
  port:        5432
  user:        "<USER>"
  password:    "<PASSWORD>"
  database:    "<DB_NAME>"

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

## Notes on the `movement` section

- `sampling_rate` is the nominal acquisition-rate reference
- `resample_hz` is the fixed interpolation/alignment frequency used before inertial windowing
- `window_size_samples` controls the analysis-window length in samples
- `min_window_fraction` allows preserving the last partial analysis window when it is large enough
- `effective_gait` can be enriched with GPS-derived metrics such as travelled distance, elapsed time, average speed, and a boolean GPS validation flag

## Validation

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

## Documentation

Full Sphinx documentation is available in `docs/`. 

To rebuild locally:

```bash
cd docs
make html
```

Then open `_build/html/index.html` in your browser.

## Contributing

1. Fork the repo  
2. Create a branch: `git checkout -b feature/your-feature`  
3. Make your changes & tests  
4. Open a Pull Request

## License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.
