.. _find_mscodeids:

find_mscodeids
==============

Utility to retrieve unique CodeIDs from InfluxDB, identify activity segments
for each device ("Left" and "Right" foot), and store them in PostgreSQL tables
(`activity_leg` and `activity_all`).

**Location:** ``ms_monitoring/find_mscodeids.py``

.. graphviz::
  :caption: Simplified Sequence for `find_mscodeids`
  :align: center

  digraph find_mscodeids_flow {
    rankdir=LR;
    graph [fontname="Helvetica"];
    node  [shape=box, fontname="Helvetica"];
    edge  [fontname="Helvetica"];

    // Actors and services
    User         [label="User"];
    CLI          [label="find_mscodeids CLI"];
    Proc         [label="CodeIDProcessor"];
    DataMgr      [label="DataManager"];
    InfluxDB     [label="InfluxDB"];
    PostgreSQL   [label="PostgreSQL"];

    // Main flow
    User      -> CLI       [label="run `python -m ms_monitoring.find_mscodeids`"];
    CLI       -> Proc      [label="__init__(config)"];

    Proc      -> DataMgr   [label="get_codeids_in_range(from,until)"];
    DataMgr   -> InfluxDB  [label="query distinct CodeIDs"];
    InfluxDB  -> DataMgr   [label="list of CodeIDs"];
    DataMgr   -> Proc      [label="return CodeID list"];

    // Process each CodeID
    Proc      -> Proc      [label="for each CodeID:\nfetch_sensor_data →\nidentify_activity_segments →\nstore_data(activity_leg & activity_all) (optional)"];

    // Storage to PostgreSQL
    Proc      -> DataMgr   [label="store_data(...) (optional)"];
    DataMgr   -> PostgreSQL[label="INSERT activity_leg & activity_all"];

    // Finish up
    Proc      -> CLI       [label="print INFO_ALL_PROCESSED"];
    CLI       -> User      [label="display summary"];
  }

Usage
-----

Run as a module:

.. code-block:: bash

    python -m ms_monitoring.find_mscodeids \
      -c config.yaml \
      -f "2024-06-01 00:00:00" \
      -u "2024-06-30 23:59:59" \
      -l en \
      --save 1 \
      -v 2 \
      --head-rows 10

Arguments
---------

- ``-c, --config``
  Path to the YAML configuration file. (required)

- ``-f, --from``
  Start datetime, format ``YYYY-MM-DD HH:MM:SS``.
  Default: midnight (00:00:00) of the previous day.

- ``-u, --until``
  End datetime, same format.
  Default: now.

- ``-l, --lang``
  Interface language (``en``, ``es``). Default: ``es``.

- ``--save``
  Persist results to PostgreSQL: ``--save 1`` (default) writes to
  ``codeids``, ``activity_leg`` and ``activity_all``; ``--save 0`` runs in dry-run mode.

- ``-v, --verbose``
  Verbosity level (0: silent, 1: info, 2: debug, 3+: trace).

- ``--head-rows``
  Number of rows to display for segment previews when verbosity ≥ 2.
  Default: 5.

Examples
--------

Basic run with defaults (yesterday 00:00 → now)::

  $ python -m ms_monitoring.find_mscodeids \
      -c config.yaml

Specify full range, English, and verbose output::

  $ python -m ms_monitoring.find_mscodeids \
      -c config.yaml \
      -f "2024-06-01 00:00:00" \
      -u "2024-06-30 23:59:59" \
      -l en \
      --save 1 \
      -v 2 \
      --head-rows 10

Dry-run (no PostgreSQL writes)::

  $ python -m ms_monitoring.find_mscodeids \
      -c config.yaml \
      -f "2024-06-01 00:00:00" \
      -u "2024-06-01 23:59:59" \
      --save 0 \
      -v 1
