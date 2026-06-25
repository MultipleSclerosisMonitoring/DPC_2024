---
layout: default
title: MS Monitoring
---

# MS Monitoring

MS Monitoring transforms raw wearable telemetry into semantic activity windows,
movement detections, and graded bilateral gait evidence.

## Project overview

The repository is organized as a two-stage blind pipeline:

1. Bottom-up semantic construction from raw wearable references.
2. Movement and graded gait detection over previously stored semantic windows.

## Key semantic outputs

- `activity_leg`
- `activity_all`
- `effective_movement`
- `effective_gait` with `gait_confidence_level`

## Documentation sections

- [Architecture](architecture)
- [Usage](usage)
- [Module reference](modules)
- [Repository README](../README.md)
- [Docs folder README](./README.md)

## Local Sphinx build

```bash
pip install -r docs/requirements.txt
cd docs
make html
```
