.. _find_gait:

find_gait
=========

Utility to detect and store effective gait periods based on segments
in the ``activity_all`` table of PostgreSQL.

**Location:** ``ms_monitoring/find_gait.py``

.. graphviz::
  :caption: Simplified Flow for `find_gait`
  :align: center

  digraph find_gait_flow {
    rankdir=LR;
    graph [fontname="Helvetica"];
    node  [shape=box, fontname="Helvetica"];
    edge  [fontname="Helvetica"];

    // Actors and services
    User         [label="User"];
    FindGait_CLI [label="find_gait CLI"];
    Movement     [label="MovementDetector"];
    DataMgr      [label="DataManager"];
    InfluxDB     [label="InfluxDB"];
    PostgreSQL   [label="PostgreSQL"];

    // Main sequence
    User -> FindGait_CLI [label="run `python -m ms_monitoring.find_gait`"];
    FindGait_CLI -> Movement [label="__init__(ids|time_window, config)"];
    Movement -> DataMgr    [label="load stored segments"];
    DataMgr -> PostgreSQL  [label="SELECT * FROM activity_all"];
    Movement -> InfluxDB   [label="fetch raw sensor data"];
    InfluxDB -> Movement   [label="raw DataFrame"];
    Movement -> Movement   [label="process segments\n(fetch → compute → detect)"];
    Movement -> DataMgr    [label="save results (optional)"];
    DataMgr -> PostgreSQL  [label="INSERT effective_movement + gait"];
    Movement -> FindGait_CLI[label="return results"];
    FindGait_CLI -> User    [label="print summaries"];
  }

Usage
-----

Run as a module from your virtual environment:

.. code-block:: bash

    # Option A: process explicit activity_all IDs
    python -m ms_monitoring.find_gait \
      -i 12,34,56 \
      -c config.yaml \
      -l en \
      --output raw_data.xlsx \
      --save 1 \
      -v 2

    # Option B: if --ids is omitted, process the last N hours (default: 25)
    python -m ms_monitoring.find_gait \
      -c config.yaml \
      --hours-back 48 \
      -l en \
      --save 0 \
      -v 1

Arguments
---------

- ``-i, --ids``
  Range/list specification of ``activity_all`` record IDs.
  Supported formats: ``1-271`` or ``1,5,10-15``.
  If omitted, the script falls back to ``--hours-back``.

- ``--hours-back``
  If ``--ids`` is omitted, look back the last N hours (UTC window).
  Default: ``25``.

- ``-c, --config``
  Path to the YAML configuration file. (required)

- ``-l, --lang``
  Interface language (``en``, ``es``). Default: ``es``.

- ``-o, --output``
  Optional path to an Excel file where raw sensor data will be exported.

- ``--save``
  Persist results to PostgreSQL: ``--save 1`` (default) writes to
  ``effective_movement`` and ``effective_gait``; ``--save 0`` runs in dry-run mode.

- ``-v, --verbose``
  Verbosity level (0: none, 1: info, 2: debug).

- ``--head-rows``
  Number of rows to display when verbosity ≥ 2. Default: 8.

Examples
--------

Detailed output, export raw data, and save to database::

  $ python -m ms_monitoring.find_gait \
      -i 12,34,56 \
      -c config.yaml \
      -l en \
      --output raw_data.xlsx \
      --save 1 \
      -v 2 \
      --head-rows 3

Dry-run (no PostgreSQL writes)::

  $ python -m ms_monitoring.find_gait \
      -i 78,90 \
      -c config.yaml \
      --save 0 \
      -v 1

Time-window mode (last 48 hours)::

  $ python -m ms_monitoring.find_gait \
      -c config.yaml \
      --hours-back 48 \
      -l en \
      --save 0 \
      -v 1
