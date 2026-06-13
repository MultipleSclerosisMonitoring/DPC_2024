---
layout: default
title: Usage
---

# Usage

This project is intended to run in two consecutive stages:

1. Build semantic candidate windows from raw wearable data.
2. Detect movement and gait over those stored semantic windows.

## Execution order

1. Run `find_mscodeids`.
2. Check that `activity_leg` and `activity_all` were created correctly.
3. Run `find_gait`.
4. Inspect `effective_movement` and `effective_gait`.
5. Optionally run the validation utilities in `tests/`.

## Stage 1: semantic construction

Use `find_mscodeids` to retrieve CodeIDs from InfluxDB and construct the
semantic tables required by the gait stage.

```bash
python -m ms_monitoring.find_mscodeids \
  -c config.yaml \
  -f "2025-05-11 00:00:00" \
  -u "2025-05-12 00:00:00" \
  --save 1 \
  -v 2
```

## Stage 2: movement and gait detection

Use `find_gait` to process previously created `activity_all` windows.

```bash
python -m ms_monitoring.find_gait \
  -c config.yaml \
  -i "152" \
  --save 1 \
  -v 2
```

You can also run it in dry mode with a recent time window:

```bash
python -m ms_monitoring.find_gait \
  -c config.yaml \
  --hours-back 25 \
  --save 0 \
  -v 1
```

## Validation

The repository includes a ground-truth validation utility based on manually
labeled windows:

```bash
python -m tests.validate_ground_truth \
  -e path/to/ground_truth.xlsx \
  -c config.yaml \
  -l es
```

## Full technical source

The complete Sphinx source remains available in
[`usage.rst`](./usage.rst).
