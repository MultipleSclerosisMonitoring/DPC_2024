Repository modules
==================

This section groups the repository into execution layers, shared services, and
supporting utilities. The goal is to make the codebase navigable before diving
into API details.

Layered view
------------

The project is organized into four layers:

1. **Shared infrastructure**
   ``msTools``
2. **Bottom-up semantic construction**
   ``msCodeID`` and ``find_mscodeids``
3. **Movement and graded gait detection**
   ``msGait`` and ``find_gait``
4. **Validation and post-hoc reporting**
   ``tests`` plus the ``verification`` scripts

There is also a lightweight operational layer for fast inventory visibility:
``check_user_tokens_multi`` plus the ``run_daily_pipeline`` wrapper.

Module relationships
--------------------

.. graphviz::
   :caption: Repository module relationships
   :align: center

   digraph repo_modules {
      rankdir=LR;
      graph [fontname="Helvetica"];
      node  [shape=box, fontname="Helvetica", style="rounded"];
      edge  [fontname="Helvetica"];

      msTools         [label="msTools\nshared infrastructure"];
      msCodeID        [label="msCodeID\nsemantic construction"];
      find_mscodeids  [label="find_mscodeids\nCLI stage 1"];
      msGait          [label="msGait\nmovement + graded gait detection"];
      find_gait       [label="find_gait\nCLI stage 2"];
      tests           [label="tests + verification\nvalidation and reporting"];

      msTools -> msCodeID;
      msTools -> msGait;
      msCodeID -> find_mscodeids;
      msGait -> find_gait;
      find_mscodeids -> find_gait;
      find_gait -> tests;
   }

Functional responsibilities
---------------------------

``msTools``
   Provides configuration loading, UTC normalization, internationalization,
   shared models, and PostgreSQL/InfluxDB access.

``msCodeID``
   Converts raw reference telemetry into semantic candidate windows that can be
   reused by downstream modules.

``find_mscodeids``
   Executes stage 1 and persists ``codeids``, ``activity_leg``, and
   ``activity_all``.

``msGait``
   Performs inertial movement detection, derives bilateral gait episodes, and
   classifies gait confidence as brief or robust before GPS enrichment.

``find_gait``
   Executes stage 2 and persists ``effective_movement`` and
   ``effective_gait``.

``tests`` and ``verification``
   Contain ground-truth validation, threshold studies, and post-hoc comparison
   scripts against external clinical test inventories.

Data products by layer
----------------------

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Layer
     - Main outputs
   * - Shared infrastructure
     - connections, settings, time normalization
   * - Semantic construction
     - ``codeids``, ``activity_leg``, ``activity_all``
   * - Movement/gait detection
     - ``effective_movement``, ``effective_gait``
   * - Validation/reporting
     - threshold studies, compatibility reports

Package pages
-------------

Shared infrastructure
~~~~~~~~~~~~~~~~~~~~~

.. toctree::
   :maxdepth: 1

   msTools

Bottom-up semantic construction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. toctree::
   :maxdepth: 1

   msCodeID
   find_mscodeids
   check_user_tokens_multi
   run_daily_pipeline

Movement and gait detection
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. toctree::
   :maxdepth: 1

   msGait
   find_gait

Repository guidance
-------------------

A useful way to read the codebase is:

1. start from :doc:`architecture`
2. understand ``msTools`` as the integration substrate
3. read ``msCodeID`` to understand how semantic candidate windows are created
4. read ``msGait`` to understand how those candidate windows become movement
   and graded gait outputs
5. inspect ``tests`` and ``verification`` when you need evidence, not just APIs
