Usage
=====

This section describes the practical execution flow of the repository. It assumes a hybrid configuration model where ``config.yaml`` holds structural settings and an optional ``.env`` file overrides local secrets.

The project is intended to be run in two consecutive stages:

1. build semantic candidate windows from raw wearable data
2. detect movement and gait over those stored semantic windows

Execution order
---------------

The normal order is:

1. run ``find_mscodeids``
2. verify that ``activity_leg`` and ``activity_all`` were created correctly
3. run ``find_gait``
4. inspect ``effective_movement`` and ``effective_gait``
5. optionally run the ground-truth validation utilities in ``tests``

Stage 1: semantic construction
------------------------------

Use ``find_mscodeids`` to retrieve CodeIDs from InfluxDB and construct the
semantic tables required by the gait stage.

Example:

.. code-block:: bash

   python -m ms_monitoring.find_mscodeids \
     -c config.yaml \
     -f "2025-05-11 00:00:00" \
     -u "2025-05-12 00:00:00" \
     --save 1 \
     -v 2

This stage may generate:

- rows in ``codeids``
- rows in ``activity_leg``
- rows in ``activity_all``

Stage 2: movement and gait detection
------------------------------------

Use ``find_gait`` to process previously created ``activity_all`` windows.

Example using explicit IDs:

.. code-block:: bash

   python -m ms_monitoring.find_gait \
     -c config.yaml \
     -i "152" \
     --save 1 \
     -v 2

Example using a recent time window:

.. code-block:: bash

   python -m ms_monitoring.find_gait \
     -c config.yaml \
     --hours-back 25 \
     --save 0 \
     -v 1

This stage may generate:

- rows in ``effective_movement``
- rows in ``effective_gait``
- GPS enrichment fields inside ``effective_gait``:
  ``gps_points``, ``gps_distance_m``, ``gps_elapsed_sec``,
  ``gps_avg_speed_m_s``, and ``gps_validated``

Dry-run workflow
----------------

Both CLI tools support a dry mode through ``--save 0``.

This is useful when you want to:

- inspect intermediate outputs without modifying PostgreSQL
- debug a time range
- validate that segmentation or gait detection behaves as expected before persistence

Validation workflow
-------------------

The repository also includes a ground-truth validation utility based on an Excel
file with manually labeled windows.

Example:

.. code-block:: bash

   python -m tests.validate_ground_truth \
     -e path/to/ground_truth.xlsx \
     -c config.yaml \
     -l es

This validation stage compares the algorithm output against manually labeled
windows and reports metrics such as:

- accuracy
- precision
- recall / sensitivity
- specificity
- F1-score
- Cohen's Kappa
- confusion matrix

Operational notes
-----------------

- timestamps are normalized before database queries
- the gait stage depends on ``activity_all`` already existing
- inertial analysis is performed on resampled data
- gait rows are GPS-enriched before final storage
- repeated executions are designed to avoid uncontrolled duplication in the
  main semantic output tables