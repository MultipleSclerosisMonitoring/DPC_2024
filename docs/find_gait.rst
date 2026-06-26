find_gait
=========

The ``find_gait`` command-line tool is the second executable stage of the
pipeline. It reads bilateral activity windows from PostgreSQL (or effective
movement records for backfill), retrieves raw inertial and GPS data from InfluxDB,
detects effective movement in each leg, derives bilateral gait episodes, classifies
them by confidence, enriches them with GPS-based metrics, and optionally stores
the results in PostgreSQL.

Purpose
-------

This command performs the movement and gait detection stage of the project:

1. retrieve candidate bilateral windows from ``activity_all`` (full mode) or existing ``effective_movement`` (fill-gait mode)
2. expand those windows into one row per leg
3. fetch raw inertial signals for each leg from InfluxDB (full mode only)
4. resample the inertial series to a fixed temporal grid (full mode only)
5. detect ``effective_movement`` from spectral and temporal criteria (full mode only)
6. intersect left and right effective movement to derive ``effective_gait``
7. assign ``gait_confidence_level`` to each bilateral episode
8. enrich gait intervals with GPS-derived metrics
9. optionally store ``effective_movement`` (full mode) and ``effective_gait``

Modes of operation
------------------

The command supports two modes via ``--mode``:

**Full mode** (``--mode full``, default)

Complete pipeline: compute movement and gait from raw sensor data.

.. code-block:: bash

   python -m ms_monitoring.find_gait \
     -c config.yaml \
     -i "1,5,10-15" \
     --mode full \
     --save 1 \
     -v 2

**Fill-gait mode** (``--mode fill-gait``)

Backfill mode: read existing ``effective_movement`` from PostgreSQL, compute
``effective_gait`` **only for records without corresponding gait**, and save
only newly computed gait.

.. code-block:: bash

   python -m ms_monitoring.find_gait \
     -c config.yaml \
     --hours-back 168 \
     --mode fill-gait \
     --save 1 \
     -v 2

Use fill-gait mode to efficiently add gait entries for historical effective_movement
records that were already calculated but lack corresponding gait due to permission
errors, schema changes, or incremental processing.

Input modes
-----------

The command supports two retrieval modes for ID/time specification.

**Explicit ID mode**

Provide one or more ``activity_all`` IDs with ``-i`` / ``--ids``:

.. code-block:: bash

   python -m ms_monitoring.find_gait \
     -c config.yaml \
     -i "1,5,10-15" \
     --mode full \
     --save 1 \
     -v 2

**Recent-hours mode**

If ``--ids`` is omitted, the command can retrieve candidate windows from a
relative lookback window using ``--hours-back``:

.. code-block:: bash

   python -m ms_monitoring.find_gait \
     -c config.yaml \
     --hours-back 25 \
     --mode full \
     --save 0 \
     -v 1

**Explicit time-window mode**

If you want a concrete interval, pass ``--from`` and ``--until``. When both are
provided they take precedence over the relative lookback window:

.. code-block:: bash

   python -m ms_monitoring.find_gait \
     -c config.yaml \
     --from "2024-01-02T10:00:00" \
     --until "2024-01-02T11:00:00" \
     --mode full \
     --save 0 \
     -v 1

Arguments
---------

The tool accepts the following arguments:

- ``-c, --config``: path to ``config.yaml`` (required)
- ``-i, --ids``: range/list of ``activity_all`` IDs
- ``-l, --lang``: interface language (``es`` or ``en``)
- ``-o, --output``: optional XLSX export of raw sensor data (full mode only)
- ``-v, --verbose``: verbosity level
- ``--head-rows``: number of preview rows to print
- ``--hours-back``: fallback lookback window when neither ``--ids`` nor an explicit ``--from/--until`` range is provided
- ``--from``: inclusive start timestamp for an explicit analysis window
- ``--until``: inclusive end timestamp for an explicit analysis window
- ``--mode``: execution mode (``full`` or ``fill-gait``, default ``full``)
- ``--save``: whether to persist results in PostgreSQL (``1``) or run in dry mode (``0``)

High-level execution flow
-------------------------

**Full mode**

The command performs the following steps:

1. initialize translations
2. create a ``MovementDetector``
3. retrieve bilateral candidate windows from ``activity_all``
4. expand them into one row per leg
5. detect per-leg ``effective_movement``
6. optionally store ``effective_movement``
7. detect bilateral ``effective_gait``
8. validate and enrich gait intervals with GPS-derived metrics
9. optionally store ``effective_gait``

**Fill-gait mode**

The command performs the following steps:

1. initialize translations
2. create a ``MovementDetector``
3. read existing ``effective_movement`` from PostgreSQL by time range
4. identify movement records without corresponding ``effective_gait``
5. compute bilateral ``effective_gait`` **only for missing entries**
6. validate and enrich gait intervals with GPS-derived metrics
7. save only newly computed ``effective_gait``

Detection details
-----------------

The inertial stage is based on:

- raw accelerometer and gyroscope signals (full mode only)
- fixed-rate resampling before analysis (full mode only)
- magnitude computation for acceleration and gyroscope (full mode only)
- Welch spectral power inside a configurable frequency band (full mode only)
- temporal continuity criteria
- merging of nearby valid windows
- minimum-duration filtering

The gait stage is based on:

- temporal overlap between left and right effective-movement intervals
- a graded confidence interpretation of bilateral overlap
- optional GPS enrichment using distance, elapsed time, average speed, and a
  boolean validation flag

Gait confidence semantics
-------------------------

``effective_gait`` is no longer purely binary.

- ``gait_confidence_level = 1`` means brief bilateral gait
- ``gait_confidence_level = 2`` means robust bilateral gait

This is useful when the pipeline is executed blindly and test compatibility is
checked later against external clinical intervals.

GPS enrichment
--------------

Each detected gait interval may be enriched with the following fields:

- ``gps_points``
- ``gps_distance_m``
- ``gps_elapsed_sec``
- ``gps_avg_speed_m_s``
- ``gps_validated``

These values are derived from the GPS trace associated with the same
participant and time interval.

Dry-run mode
------------

When ``--save 0`` is used:

- the full detection pipeline is still executed
- results are printed for inspection
- no rows are written to PostgreSQL

Typical outputs
---------------

The command may generate:

- per-leg rows in ``effective_movement``
- bilateral rows in ``effective_gait`` enriched with GPS metrics
- graded gait evidence through ``gait_confidence_level``

Implementation notes
--------------------

- timestamps are normalized consistently before querying the databases
- inertial data is resampled before windowing to mitigate packet loss and
  improve temporal alignment
- the final partial inertial window can be kept when it is large enough
- GPS enrichment is part of the final pipeline before storing
  ``effective_gait``
- post-hoc compatibility reports can later interpret ``effective_gait`` as
  ``none``, ``brief``, or ``robust`` depending on the confidence level

API reference
-------------

.. automodule:: ms_monitoring.find_gait
   :members:
   :undoc-members:
   :show-inheritance:
