msTools package
===============

The ``msTools`` package provides the shared infrastructure used by the rest of
the repository.

It centralizes configuration loading, time normalization,
internationalization, data validation through Pydantic models, and database
access for both InfluxDB and PostgreSQL.

Architecture overview
---------------------

.. graphviz::
   :caption: Shared infrastructure and integration points
   :align: center

   digraph class_msTools {
      rankdir=TB;
      graph [fontname="Helvetica"];
      node  [shape=record, fontname="Helvetica"];
      edge  [fontname="Helvetica"];

      DataManager [label="{DataManager|
        + load_config(...)\l
        + get_config(...)\l
        + get_influx_client()\l
        + get_codeids_in_range(...)\l
        + fetch_data(...)\l
        + segments_retrieval(...)\l
        + recover_activity_all(...)\l
        + store_codeid(...)\l
        + transform_activityleg(...)\l
        + store_data(...)\l
      }"];

      Models [label="{Pydantic models|CodeID\lActivityLeg\lActivityAll\lEffectiveMovement\lEffectiveGait\l}"];
      TimeUtils [label="{timeutils|ensure_utc(...)\l}"];
      I18N [label="{i18n|gettext helpers\ltranslation setup\l}"];
      Settings [label="{settings|typed config\l.env overrides\l}"];

      DataManager -> Models;
      DataManager -> TimeUtils;
      DataManager -> I18N;
      DataManager -> Settings;
   }

Core components
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
- ensuring the ``effective_gait`` schema can persist the unified
  ``gait_confidence_level`` field
- updating GPS-related fields in ``effective_gait`` when required

``settings`` (``msTools.settings``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides typed runtime settings and configuration-path helpers for loading
``config.yaml`` with optional ``.env`` overrides.

``models`` (``msTools.models``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Defines shared Pydantic models used before PostgreSQL insertion.

``timeutils`` (``msTools.timeutils``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides ``ensure_utc(...)`` to normalize timestamps consistently before
querying InfluxDB or PostgreSQL.

``i18n`` (``msTools.i18n``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides lightweight translation helpers for CLI-facing messages.

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
   - ``effective_gait`` rows may be enriched with GPS metrics and now also
     carry a graded confidence level

Configuration
-------------

The runtime configuration follows a hybrid model:

- ``config.yaml`` stores structural and algorithm settings
- ``.env`` can override local secrets and connection values
- environment variables override both when present

The package reads configuration from ``config.yaml``, with optional overrides
from a local ``.env`` file. The repository includes ``.env.example`` as a
reference template.

Notes
-----

- semantic timestamps are handled with timezone awareness
- database inserts are validated with Pydantic models
- the storage logic is idempotent for the main semantic tables
- ``effective_gait`` includes both GPS enrichment fields and
  ``gait_confidence_level``

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
