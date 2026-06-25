.. MS Monitoring documentation master file

MS Monitoring Documentation
===========================

MS Monitoring is a repository for turning raw wearable telemetry into reusable
semantic outputs for multiple sclerosis monitoring studies. Its purpose is not
to deliver a standalone validated clinical gait instrument, but to provide a
transparent semantic transformation layer that supports downstream clinical
analysis, interoperability, and longitudinal reasoning.

The codebase is intentionally split into two executable stages:

1. bottom-up semantic construction from raw wearable references
2. inertial movement and gait analysis over previously built semantic windows

What the repository does
------------------------

At a high level, the repository starts from raw device measurements and ends in
progressively more interpretable artefacts:

- ``codeids``: participants observed in the queried time range, optionally enriched with fast inventory metadata
- ``activity_leg``: per-foot semantic activity windows
- ``activity_all``: bilateral candidate windows built from left/right overlap
- ``effective_movement``: per-leg movement detections derived from inertial data
- ``effective_gait``: bilateral gait detections enriched with GPS-derived metrics
- optional clinical-test annotations aligned later as a higher semantic layer

The gait stage now exposes a unified confidence model:

- ``gait_confidence_level = 1``: brief bilateral gait
- ``gait_confidence_level = 2``: robust bilateral gait

This distinction is especially useful when clinical compatibility is checked
*after* the blind pipeline has already run. Short tests such as TUG or T25FW
can now be represented as brief bilateral gait instead of being collapsed into
``none``.

Repository scope
----------------

The repository covers the following functional concerns:

- configuration loading with YAML + optional ``.env`` overrides
- PostgreSQL and InfluxDB access
- timezone normalization and translated CLI output
- bottom-up semantic segmentation from raw reference streams
- inertial movement detection using spectral and temporal criteria
- bilateral gait derivation from left/right overlap
- GPS enrichment and plausibility validation
- CLI execution, dry runs, and validation utilities

High-Level Pipeline
-------------------

.. graphviz::
   :caption: End-to-end flow from raw telemetry to semantic outputs
   :align: center

   digraph overview {
      rankdir=LR;
      graph [fontname="Helvetica"];
      node  [shape=box, fontname="Helvetica", style="rounded"];
      edge  [fontname="Helvetica"];

      Influx      [label="InfluxDB\nraw telemetry"];
      FindCodeIDs [label="find_mscodeids CLI"];
      ActivityLeg [label="activity_leg"];
      ActivityAll [label="activity_all"];
      FindGait    [label="find_gait CLI"];
      EffMove     [label="effective_movement"];
      EffGait     [label="effective_gait\n(level 1 = brief,\nlevel 2 = robust)"];
      Checks      [label="post-hoc clinical\ncompatibility checks"];

      Influx -> FindCodeIDs -> ActivityLeg -> ActivityAll -> FindGait -> EffMove -> EffGait -> Checks;
   }

Documentation Map
-----------------

Use the following sections depending on what you need:

- :doc:`architecture` for system-level context and UML-style diagrams
- :doc:`usage` for operational execution order and dry-run workflows
- :doc:`modules` for package-by-package structure and responsibilities
- package pages such as :doc:`msTools`, :doc:`msCodeID`, and :doc:`msGait`
  for API-focused details

Contents
--------

.. toctree::
   :maxdepth: 2
   :caption: Sections

   architecture
   usage
   modules
   check_user_tokens_multi
   run_daily_pipeline

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
