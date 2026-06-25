run_daily_pipeline
==================

The ``run_daily_pipeline`` command is the cron-oriented orchestration wrapper
for the repository's blind semantic pipeline.

Purpose
-------

The wrapper exists to make daily production execution deterministic and
verifiable.

Instead of relying on the stage CLIs' convenience defaults, it:

1. computes a closed time window
2. runs ``find_mscodeids`` with explicit boundaries
3. reads the relevant ``activity_all`` identifiers from PostgreSQL
4. runs ``find_gait`` on those identifiers

Default behavior
----------------

By default, the command processes the **previous closed day in
``Europe/Madrid``**.

That makes the resulting execution:

- deterministic
- auditable
- easy to re-run for a specific day
- more robust than recent-hours retrieval for ``find_gait``

Arguments
---------

- ``-c, --config``: path to ``config.yaml``
- ``--day``: closed local day in ``YYYY-MM-DD`` format
- ``-f, --from`` and ``-u, --until``: explicit override for the closed window
- ``-l, --lang``: language forwarded to the wrapped CLIs
- ``--save``: whether the wrapped commands persist to PostgreSQL
- ``--head-rows``: preview row count forwarded to the wrapped CLIs
- ``--gait-batch-size``: number of ``activity_all`` IDs per gait subprocess
- ``-v, --verbose``: verbosity level

Examples
--------

.. code-block:: bash

   python -m ms_monitoring.run_daily_pipeline \
     -c config.yaml \
     --save 1 \
     -v 1

.. code-block:: bash

   python -m ms_monitoring.run_daily_pipeline \
     -c config.yaml \
     --day 2026-06-24 \
     --save 1 \
     -v 1

API reference
-------------

.. automodule:: ms_monitoring.run_daily_pipeline
   :members:
   :undoc-members:
   :show-inheritance:
