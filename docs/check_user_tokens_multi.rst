check_user_tokens_multi
=======================

The ``check_user_tokens_multi`` command is the lightweight inventory entry
point of the repository. It scans one or more InfluxDB buckets for recently
observed ``CodeID`` values and synchronizes them into PostgreSQL without
running the full semantic pipeline.

Purpose
-------

This command is intended for operational visibility rather than semantic
construction.

It is useful when you need to:

- make newly observed ``CodeID`` values visible quickly
- support Grafana or operational dashboards
- enrich ``codeids`` with optional inventory metadata
- keep frequent cron executions lightweight

Arguments
---------

- ``-c, --config``: path to ``config.yaml``
- ``-f, --from``: optional inclusive start timestamp
- ``-u, --until``: optional exclusive end timestamp
- ``--lookback-minutes``: fallback recent window when ``--from`` is omitted
- ``-b, --buckets``: comma-separated bucket list
- ``--bucket-measurements``: explicit ``bucket=measurement1,measurement2`` definitions
- ``--table``: destination PostgreSQL table (default: ``codeids``)
- ``--dry-run``: compute the synchronization plan without writing
- ``--fail-on-anomaly``: abort on conflicting inventory metadata
- ``-v, --verbose``: verbosity level

Behavior
--------

The command preserves the repository's semantic assumption that one row in
``codeids`` still represents one ``codeid``.

If the table contains the optional inventory metadata columns, the command may
also maintain:

- ``type``
- ``bucket``
- ``first_seen_at``
- ``last_seen_at``

If a previously known ``codeid`` is observed with conflicting metadata, the
command reports an anomaly instead of duplicating the row.

Example
-------

.. code-block:: bash

   python -m ms_monitoring.check_user_tokens_multi \
     -c config.yaml \
     -b "Gait/autogen,MbientLab/autogen,SmartBand/autogen" \
     --lookback-minutes 15 \
     -v 1

API reference
-------------

.. automodule:: ms_monitoring.check_user_tokens_multi
   :members:
   :undoc-members:
   :show-inheritance:
