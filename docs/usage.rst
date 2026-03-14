.. _usage:

Usage
=====

After installing the **ms_monitoring** package, run the CLI scripts as Python modules.
The typical workflow is:

1. **Retrieve and store CodeIDs and activity segments**
2. **Detect effective movement windows and gait episodes**

Retrieving CodeIDs and Activity Segments
----------------------------------------

Retrieves unique CodeIDs from InfluxDB within a specified date range, identifies
activity segments for each foot, and stores them in PostgreSQL tables
(`activity_leg` and `activity_all`).

.. code-block:: console

    python -m ms_monitoring.find_mscodeids \
      -c config.yaml \
      -f "2024-06-01 00:00:00" \
      -u "2024-06-30 23:59:59" \
      -l en \
      --save 1 \
      -v 2 \
      --head-rows 10

For full argument details and examples, see :ref:`find_mscodeids`.

Detecting Effective Movement and Gait
-------------------------------------

Analyzes stored activity segments to detect effective movement windows for each
foot and overlapping gait episodes, optionally exporting raw sensor data and
saving results back to the database.

.. code-block:: console

    # Option A: process explicit activity_all IDs
    python -m ms_monitoring.find_gait \
      -i 12,34,56 \
      -c config.yaml \
      -l en \
      --output raw_data.xlsx \
      --save 1 \
      -v 2 \
      --head-rows 5

    # Option B: if --ids is omitted, process the last N hours (default: 25)
    python -m ms_monitoring.find_gait \
      -c config.yaml \
      --hours-back 48 \
      -l en \
      --save 0 \
      -v 1

For full argument details and examples, see :ref:`find_gait`.
