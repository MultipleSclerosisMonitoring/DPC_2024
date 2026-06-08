find_mscodeids
==============

The ``find_mscodeids`` command-line tool is the first executable stage of the
pipeline. It retrieves distinct CodeIDs from InfluxDB for a given time range,
builds per-leg semantic segments, and stores the resulting ``activity_leg`` and
``activity_all`` records in PostgreSQL.

Purpose
-------

This command is responsible for the bottom-up semantic construction described
in the project:

1. retrieve the CodeIDs present in a time window
2. fetch reference wearable data for each CodeID
3. segment the activity separately for the left and right foot
4. store the per-leg segments as ``activity_leg``
5. compute left/right overlaps and store them as ``activity_all``

This stage prepares the candidate bilateral windows that are later consumed by
``find_gait``.

Arguments
---------

The tool accepts the following arguments:

- ``-c, --config``: path to ``config.yaml`` (required)
- ``-f, --from``: start datetime of the query window
- ``-u, --until``: end datetime of the query window
- ``-l, --lang``: interface language (``es`` or ``en``)
- ``-v, --verbose``: verbosity level
- ``--head-rows``: number of preview rows when verbose output is enabled
- ``--save``: whether to persist results in PostgreSQL (``1``) or run in dry mode (``0``)

If ``--from`` is omitted, the tool defaults to the previous day at
``00:00:00``. If ``--until`` is omitted, it defaults to the current time.

High-level execution flow
-------------------------

The command performs the following steps:

1. initialize translations
2. load configuration and create the shared ``DataManager``
3. retrieve distinct CodeIDs from InfluxDB
4. store each CodeID in PostgreSQL if needed
5. fetch the wearable reference stream for that CodeID
6. build left/right leg segments from raw data
7. prepare and optionally store ``activity_leg``
8. build bilateral overlaps and optionally store ``activity_all``

Dry-run mode
------------

When ``--save 0`` is used:

- the command still performs the complete computation
- results are printed for inspection
- no rows are written to PostgreSQL
- placeholder IDs are used internally when needed for downstream merging

Example usage
-------------

.. code-block:: bash

   python -m ms_monitoring.find_mscodeids \
     -c config.yaml \
     -f "2025-05-11 00:00:00" \
     -u "2025-05-12 00:00:00" \
     --save 1 \
     -v 2

Typical outputs
---------------

The command may generate:

- new rows in ``codeids``
- per-foot rows in ``activity_leg``
- bilateral rows in ``activity_all``

Rows with no valid segments for one foot are handled gracefully. In that case,
the missing foot is reported and only the valid semantic outputs are produced.

Implementation notes
--------------------

- timestamps are normalized through ``ensure_utc(...)``
- segment construction is gap-based
- zero-duration segments are filtered out
- bilateral activity is built through temporal overlap between left and right
  leg segments
- storage goes through ``DataManager.store_data(...)`` with validation and
  idempotent behaviour for the semantic tables

API reference
-------------

.. automodule:: ms_monitoring.find_mscodeids
   :members:
   :undoc-members:
   :show-inheritance: