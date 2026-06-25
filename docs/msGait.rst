msGait package
==============

The ``msGait`` package implements the movement and gait detection stage of the
repository.

Its role is to retrieve raw inertial and GPS data for previously identified
semantic windows, detect effective movement at leg level, derive bilateral gait
episodes, classify those episodes by confidence, enrich them with GPS-based
metrics, and optionally persist the results in PostgreSQL.

Responsibilities
----------------

The package centers on the ``MovementDetector`` class, which is responsible for:

- retrieving bilateral candidate windows from ``activity_all``
- expanding those windows into one row per leg
- fetching raw inertial data from InfluxDB for each leg
- resampling inertial signals to a fixed temporal grid
- computing acceleration and gyroscope magnitudes
- detecting ``effective_movement`` using spectral and temporal criteria
- deriving bilateral ``effective_gait`` from left/right overlap
- assigning ``gait_confidence_level`` to each gait row
- enriching gait intervals with GPS-derived metrics
- storing ``effective_movement`` and ``effective_gait`` in PostgreSQL

Class view
----------

.. graphviz::
   :caption: MovementDetector responsibilities
   :align: center

   digraph class_msGait {
      rankdir=TB;
      graph [fontname="Helvetica"];
      node  [shape=record, fontname="Helvetica"];
      edge  [fontname="Helvetica"];

      MovementDetector [label="{MovementDetector|
        + fetch_sensor_data(...)\l
        + fetch_gps_data(...)\l
        + resample_sensor_data(...)\l
        + calculate_magnitude(...)\l
        + detect_effective_movement(...)\l
        + detect_effective_gait(...)\l
        + validate_gait_with_gps(...)\l
        + save_to_postgresql(...)\l
      }"];

      DataManager [label="{DataManager|
        + segments_retrieval(...)\l
        + recover_activity_all(...)\l
        + get_influx_client()\l
        + store_data(...)\l
      }"];

      EffectiveMovement [label="{effective_movement|per-leg movement rows}"];
      EffectiveGait [label="{effective_gait|bilateral rows\lgait_confidence_level\lgps_*\l}"];

      MovementDetector -> DataManager;
      MovementDetector -> EffectiveMovement;
      MovementDetector -> EffectiveGait;
   }

Detection pipeline
------------------

The current gait-detection flow is:

1. read previously built bilateral activity windows from ``activity_all``
2. expand each bilateral window into leg-specific rows using
   ``recover_activity_all``
3. fetch raw inertial signals (``Ax``, ``Ay``, ``Az``, ``Gx``, ``Gy``, ``Gz``)
   from InfluxDB
4. resample each segment to a fixed frequency (``resample_hz``)
5. compute acceleration and gyroscope magnitudes
6. split the resampled signal into fixed-size analysis windows
7. detect ``effective_movement`` using:

- Welch band-power criteria
- temporal continuity/activity criteria

8. merge temporally adjacent valid windows and filter by minimum duration
9. derive bilateral ``effective_gait`` from the temporal overlap between left
   and right ``effective_movement`` periods
10. assign a confidence level to each gait episode
11. enrich gait rows with GPS-derived metrics

Confidence semantics
--------------------

The package now uses a unified gait-confidence model.

``gait_confidence_level = 1``
   Brief bilateral gait. The overlap is strong enough to be worth reporting but
   does not satisfy the stricter robust-gait threshold.

``gait_confidence_level = 2``
   Robust bilateral gait. The overlap satisfies ``min_gait_duration_sec``.

Conceptually, the blind detector now produces richer evidence that can later be
used by post-hoc clinical compatibility checks without forcing everything into a
binary gait/no-gait decision.

How it fits into the repository workflow
----------------------------------------

Stage 1: semantic construction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handled by ``msCodeID`` and ``find_mscodeids``.

This first stage builds:

- ``codeids``
- ``activity_leg``
- ``activity_all``

Stage 2: movement and gait detection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handled by ``msGait`` and ``find_gait``.

This second stage consumes ``activity_all`` and produces:

- ``effective_movement``
- ``effective_gait``
- GPS-enriched gait metrics
- graded gait confidence for downstream compatibility analysis

Configuration
-------------

``msGait`` reads its parameters from the ``movement`` section of
``config.yaml``. Connection values can be overridden through ``.env`` using the
keys documented in ``.env.example``.

Example:

.. code-block:: yaml

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

Parameter notes
~~~~~~~~~~~~~~~

- ``sampling_rate`` is the nominal acquisition-rate reference.
- ``resample_hz`` is the fixed interpolation/alignment frequency used before
  segment windowing and Welch analysis.
- ``window_size_samples`` controls the analysis-window length in samples.
- ``min_window_fraction`` allows preserving the last partial segment when large
  enough.
- ``min_effective_duration_sec`` filters short leg-specific detections while
  still preserving short but meaningful movement episodes.
- ``min_gait_duration_sec`` defines the robust bilateral gait threshold.
- brief bilateral gait is emitted with ``gait_confidence_level = 1`` when the
  overlap is below the robust threshold but still meaningful.
- GPS parameters define the plausibility rules used to set ``gps_validated``.

Stored outputs
--------------

``effective_movement``
~~~~~~~~~~~~~~~~~~~~~~

Per-leg movement detections with:

- ``codeid_id``
- ``start_time``
- ``end_time``
- ``duration``
- ``leg``

``effective_gait``
~~~~~~~~~~~~~~~~~~

Bilateral gait detections with:

- ``codeid_id``
- ``start_time``
- ``end_time``
- ``duration``
- ``gait_confidence_level``
- ``gps_points``
- ``gps_distance_m``
- ``gps_elapsed_sec``
- ``gps_avg_speed_m_s``
- ``gps_validated``

Python usage
------------

.. code-block:: python

   from msGait.movement_detector import MovementDetector

   detector = MovementDetector(
       config_file="config.yaml",
       ids=[152],
       verbose=1,
   )

   df_effective = detector.detect_effective_movement(
       activity_windows=detector.df_legs,
       output_filename=None,
       verbose=1,
   )

   df_gait = detector.detect_effective_gait(df_effective, verbose=1)
   df_gait = detector.validate_gait_with_gps(df_gait, verbose=1)

   detector.save_to_postgresql("effective_movement", df_effective, verbose=1)
   detector.save_to_postgresql("effective_gait", df_gait, verbose=1)

   detector.close()

Notes
-----

- inertial analysis is performed on resampled data
- the final partial analysis window may be kept when large enough
- GPS enrichment is part of the final pipeline before storing
  ``effective_gait``
- this package depends on ``msTools`` for shared infrastructure and database
  access

API reference
-------------

.. automodule:: msGait.movement_detector
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: msGait.models
   :members:
   :undoc-members:
   :show-inheritance:
