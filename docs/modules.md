---
layout: default
title: Modules
---

# Repository modules

The repository is organized into four layers:

1. Shared infrastructure in `msTools`.
2. Bottom-up semantic construction in `msCodeID` and `find_mscodeids`.
3. Movement and graded gait detection in `msGait` and `find_gait`.
4. Validation and reporting in `tests` and `verification`.

## How the pieces fit together

- `msTools` provides configuration loading, UTC normalization, translations,
  models, and database access.
- `msCodeID` constructs semantic candidate windows from raw reference streams.
- `find_mscodeids` executes stage 1 and stores `activity_leg` and `activity_all`.
- `msGait` performs per-leg movement detection and graded bilateral gait detection.
- `find_gait` executes stage 2 and stores `effective_movement` and `effective_gait`.
- `tests` and `verification` provide validation and post-hoc compatibility reports.

## Full technical source

The complete Sphinx source remains available in [`modules.rst`](./modules.rst).
