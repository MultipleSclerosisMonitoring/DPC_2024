---
layout: default
title: MS Monitoring
---

# MS Monitoring

Modular Python utilities for processing wearable-device data in multiple
sclerosis monitoring studies.

## Project overview

The repository is organized around a two-stage pipeline:

1. Bottom-up semantic construction from raw wearable references.
2. Movement and gait detection over previously stored semantic windows.

## Documentation sections

- [Usage](usage)
- [Module reference](modules)
- [Repository README](../README.md)

## Local build

The full technical documentation is maintained with Sphinx inside `docs/`.

```bash
cd docs
make html
```

The generated site will be available at `_build/html/index.html`.

The original Sphinx source files remain available in this same directory for
deeper technical reference and API details.
