msTools package
===============

The ``msTools`` package provides the shared infrastructure used by the rest of
the repository. It centralizes configuration loading, time normalization,
internationalization, data validation through Pydantic models, database access for both InfluxDB and PostgreSQL, and typed runtime settings loaded from ``config.yaml`` plus optional ``.env`` overrides.

Architecture Overview
---------------------

.. graphviz::
   :caption: DataManager and shared utilities
   :align: center

   digraph class_msTools {
      rankdir=TB;
      graph [fontname="Helvetica"];
      node  [shape=record, fontname="Helvetica"];
      edge  [fontname="Helvetica"];

      DataManager [label="{DataManager|
        + __init__(config_path)\l
        + load_config(config_path)\l
        + get_config(sect)\l
        + get_influx_client()\l
        + get_codeids_in_range(start_datetime, end_datetime)\l
        + fetch_data(query)\l
        + segments_retrieval(fstart, fend, ids, verbose)\l
        + recover_activity_all(act, verbose)\l
        + store_codeid(codeid, verbose)\l
        + transform_activityleg(data)\l
        + store_data(table_name, data, verbose)\l
        + get_real_codeid(codeid_id)\l
        + get_codeid_id_by_value(codeid)\l
        + get_record_all_legs(clegs, clname)\l
        + get_activity_ids_by_start_date_range(start_datetime, end_datetime)\l
        + close_pg()\l
        + close_influxdb()\l
        + close_all()\l
      }"];

      Models [label="{Pydantic models|
        CodeID\l
        ActivityLeg\l
        ActivityAll\l
      }"];

      TimeUtils [label="{timeutils|
        + ensure_utc(ts)\l
      }"];

      I18N [label="{i18n|
        + detect_language(...)\l
        + available_languages(...)\l
        + init_translation(...)\l
        + set_locale_for_formatting(...)\l
        + gettext(...)\l
      }"];

      DataManager -> Models;
      DataManager -> TimeUtils;
      DataManager -> I18N;
   }

Core Components
---------------

``DataManager`` (``msTools.data_manager``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``DataManager`` is the main integration layer of the project.

Its responsibilities include:

- loading project configuration from ``config.yaml``
- opening and closing PostgreSQL and InfluxDB connections
- retrieving CodeIDs from InfluxDB
- retrieving bilateral ``activity_all`` windows from PostgreSQL
- expanding bilateral windows into one row per leg
- validating rows with Pydantic before insertion
- storing semantic tables with idempotent behaviour for the main outputs
- updating GPS-related fields in ``effective_gait`` when required

Important public methods include:

- ``__init__(config_path: str) -> None``
- ``load_config(config_path: str) -> dict[str, Any]``
- ``get_config(sect: str) -> dict[str, Any] | None``
- ``get_influx_client() -> InfluxDBClient``
- ``get_codeids_in_range(start_datetime: str, end_datetime: str) -> list[str]``
- ``fetch_data(query: str) -> pandas.DataFrame``
- ``segments_retrieval(fstart: str | None = None, fend: str | None = None, ids: list[int] | None = None, verbose: int = 0) -> pandas.DataFrame``
- ``recover_activity_all(act: pandas.DataFrame, verbose: int = 0) -> pandas.DataFrame``
- ``store_codeid(codeid: str, verbose: int = 0) -> tuple[int, bool]``
- ``transform_activityleg(data: pandas.DataFrame) -> pandas.DataFrame``
- ``store_data(table_name: str, data: pandas.DataFrame, verbose: int = 1) -> list[int]``
- ``get_real_codeid(codeid_id: int) -> str``
- ``get_codeid_id_by_value(codeid: str) -> int | None``
- ``get_record_all_legs(clegs: set, clname: str = "codeleg_ids") -> pandas.DataFrame``
- ``get_activity_ids_by_start_date_range(start_datetime: str | datetime, end_datetime: str | datetime) -> list[int]``
- ``close_pg() -> None``
- ``close_influxdb() -> None``
- ``close_all() -> None``

``settings`` (``msTools.settings``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module provides typed runtime settings and configuration-path helpers for
loading ``config.yaml`` with optional ``.env`` overrides.

``models`` (``msTools.models``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The shared Pydantic models used before PostgreSQL insertion are:

- ``CodeID``
- ``ActivityLeg``
- ``ActivityAll``

These models help validate semantic records before they are persisted.

``timeutils`` (``msTools.timeutils``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module provides:

- ``ensure_utc(ts: str | pandas.Timestamp | datetime) -> pandas.Timestamp``

It is used to normalize timestamps consistently before querying InfluxDB or
PostgreSQL. Naive timestamps are interpreted as Europe/Madrid local time and
then converted to UTC.

``i18n`` (``msTools.i18n``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module provides lightweight internationalization helpers based on
``gettext``:

- ``detect_language(...)``
- ``available_languages(...)``
- ``init_translation(...)``
- ``set_locale_for_formatting(...)``
- ``gettext(...)``

It allows the CLI tools and other modules to expose translated messages while
keeping a single shared implementation.

How ``msTools`` fits into the pipeline
--------------------------------------

The package supports both main repository stages.

1. **Bottom-up semantic construction**

   - raw wearable data is queried from InfluxDB
   - ``activity_leg`` is built per foot
   - bilateral overlaps are merged into ``activity_all``

2. **Movement and gait detection**

   - ``activity_all`` windows are read from PostgreSQL
   - bilateral windows are expanded into per-leg rows
   - downstream modules derive ``effective_movement``
   - bilateral gait events are stored in ``effective_gait``
   - ``effective_gait`` rows may be enriched with GPS metrics such as
     travelled distance, elapsed time, average speed, and validation flag

Configuration
-------------

The runtime configuration follows a hybrid model:

- ``config.yaml`` stores structural and algorithm settings
- ``.env`` can override local secrets and connection values
- environment variables override both when present


The package reads configuration from ``config.yaml``, with optional overrides from a local ``.env`` file. The repository includes ``.env.example`` as a documented template.

Example:

.. code-block:: yaml

   influxdb:
     url: "https://<HOST>:8086"
     token: "<YOUR_TOKEN>"
     org: "<ORG>"
     bucket: "<BUCKET>"
     measurement: "<MEASUREMENT>"
     verify: false
     timeout: 900000

   postgresql:
     host: "<PG_HOST>"
     port: 5432
     user: "<USER>"
     password: "<PASSWORD>"
     database: "<DB_NAME>"

Notes
-----

- Semantic timestamps are handled with timezone awareness.
- Database inserts are validated with Pydantic models.
- The storage logic is idempotent for the main semantic tables.
- ``effective_gait`` can include GPS enrichment fields:
  ``gps_points``, ``gps_distance_m``, ``gps_elapsed_sec``,
  ``gps_avg_speed_m_s``, and ``gps_validated``.

API Reference
-------------

Data manager
~~~~~~~~~~~~

.. automodule:: msTools.data_manager
   :members:
   :undoc-members:
   :show-inheritance:

Models
~~~~~~

.. automodule:: msTools.models
   :members:
   :undoc-members:
   :show-inheritance:

Time utilities
~~~~~~~~~~~~~~

.. automodule:: msTools.timeutils
   :members:
   :undoc-members:
   :show-inheritance:

Settings
~~~~~~~~

.. automodule:: msTools.settings
   :members:
   :undoc-members:
   :show-inheritance:

Internationalization
~~~~~~~~~~~~~~~~~~~~

.. automodule:: msTools.i18n
   :members:
   :undoc-members:
   :show-inheritance: