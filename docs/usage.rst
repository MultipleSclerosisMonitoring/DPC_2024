Usage
=====

This section describes the operational workflow of the repository in English,
including the newer graded gait semantics.

Execution model
---------------

The project now exposes two operational layers:

1. lightweight inventory synchronization for newly observed ``codeids``
2. the two-stage semantic pipeline for activity, movement, and gait

The semantic pipeline itself is still meant to run in two stages:

1. build semantic candidate windows from raw wearable data
2. detect movement and graded gait over those stored semantic windows

Normal execution order
----------------------

1. optionally run ``check_user_tokens_multi`` as a fast inventory sync
2. run ``find_mscodeids``
3. verify that ``activity_leg`` and ``activity_all`` were created correctly
4. run ``find_gait``
5. inspect ``effective_movement`` and ``effective_gait``
6. optionally run validation or compatibility reports in ``tests`` and
   ``verification``

Stage 1: semantic construction
------------------------------

Use ``find_mscodeids`` to retrieve CodeIDs from InfluxDB and construct the
semantic tables required by the gait stage.

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
- optional updates to ``codeids.first_seen_at`` and ``codeids.last_seen_at``

Fast inventory synchronization
------------------------------

Use ``check_user_tokens_multi`` when you need a lightweight operational scan of
recently observed ``CodeID`` values without running the full semantic pipeline.
This is suitable for frequent cron execution and early Grafana visibility.

.. code-block:: bash

   python -m ms_monitoring.check_user_tokens_multi      -c config.yaml      -b "Gait/autogen,MbientLab/autogen,SmartBand/autogen"      --lookback-minutes 15      -v 1

When the ``codeids`` table contains the optional inventory metadata columns,
this command can maintain:

- ``type``
- ``bucket``
- ``first_seen_at``
- ``last_seen_at``

Daily closed-window orchestration
---------------------------------

For regular production scheduling, prefer the wrapper ``run_daily_pipeline``
instead of relying on the individual CLIs' convenience defaults.

By default, the wrapper processes the **previous closed day in
``Europe/Madrid``**, runs ``find_mscodeids`` with explicit boundaries, reads
``activity_all`` IDs from PostgreSQL, and then runs ``find_gait`` on those IDs.

.. code-block:: bash

   python -m ms_monitoring.run_daily_pipeline      -c config.yaml      --save 1      -v 1

You can also target a specific closed day:

.. code-block:: bash

   python -m ms_monitoring.run_daily_pipeline      -c config.yaml      --day 2026-06-24      --save 1      -v 1

This wrapper is the recommended basis for daily cron scheduling because it is:

- deterministic
- auditable
- aligned with the repository's blind-processing semantics
- more verifiable than ``find_gait`` recent-hours mode

Stage 2: movement and gait detection
------------------------------------

Use ``find_gait`` to process previously created ``activity_all`` windows.

.. code-block:: bash

   python -m ms_monitoring.find_gait \
     -c config.yaml \
     -i "152" \
     --save 1 \
     -v 2

If explicit IDs are omitted, the command can operate on a recent time window:

.. code-block:: bash

   python -m ms_monitoring.find_gait \
     -c config.yaml \
     --hours-back 25 \
     --save 0 \
     -v 1

This stage may generate:

- rows in ``effective_movement``
- rows in ``effective_gait``
- GPS enrichment fields inside ``effective_gait``
- ``gait_confidence_level`` where:

  - ``1`` means brief bilateral gait
  - ``2`` means robust bilateral gait

Post-hoc compatibility workflow
--------------------------------

The repository does not identify clinical tests during the blind signal
processing stages. Test compatibility is checked later as a reporting step.

That means downstream analyses should now distinguish between:

- ``none``: no bilateral gait evidence
- ``brief``: short bilateral gait compatible with short tests
- ``robust``: stronger bilateral gait satisfying the stricter threshold

The verification utilities in ``verification/`` implement this idea for Excel
coverage reviews and threshold studies.

Dry-run workflow
----------------

Both CLI tools support a dry mode through ``--save 0``.

Dry runs are useful when you want to:

- inspect intermediate outputs without modifying PostgreSQL
- debug a time range
- compare thresholds or confidence semantics
- validate that segmentation or gait detection behaves as expected before
  persistence

Validation workflow
-------------------

The repository includes empirical validation utilities based on manually
labeled windows.

.. code-block:: bash

   python -m tests.validate_ground_truth \
     -e path/to/ground_truth.xlsx \
     -c config.yaml \
     -l en

This validation stage compares algorithm outputs against manually labeled
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
- ``min_effective_duration_sec`` now defaults to ``3.0`` in the reference
  configuration to preserve short but meaningful movement episodes
- graded gait semantics are applied after bilateral overlap detection
- repeated executions are designed to avoid uncontrolled duplication in the
  main semantic output tables
