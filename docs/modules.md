---
layout: default
title: Modules
---

# Repository modules

The project is organized into four main layers:

1. Shared infrastructure in `msTools`.
2. Bottom-up semantic construction in `msCodeID` and `find_mscodeids`.
3. Movement and gait detection in `msGait` and `find_gait`.
4. Validation and supporting utilities in `tests`.

## How the pieces fit together

`msTools` provides configuration loading, UTC normalization, internationalization,
shared models, and database access.

`msCodeID` implements the bottom-up construction of semantic activity windows
from raw wearable references.

`find_mscodeids` runs the first executable pipeline stage and stores
`activity_leg` and `activity_all`.

`msGait` implements inertial movement detection, bilateral gait derivation, and
GPS enrichment.

`find_gait` runs the second executable pipeline stage and stores
`effective_movement` and `effective_gait`.

`tests` contains empirical validation utilities based on manually labeled
ground-truth windows.

## Full technical source

The complete Sphinx source remains available in
[`modules.rst`](./modules.rst).
