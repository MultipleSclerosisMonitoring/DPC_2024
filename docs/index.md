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

## Published documentation

This page is the GitHub Pages landing page published from `/docs` with Jekyll.

For the full technical documentation built with Sphinx, use Read the Docs or
build the site locally from `docs/index.rst`.

## Documentation sections

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

The generated Sphinx site will be available at `_build/html/index.html`.
