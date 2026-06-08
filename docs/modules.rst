Repository modules
==================

This section groups the main repository components into their functional roles
inside the pipeline.

Overview
--------

The project is organized into four main layers:

1. **Shared infrastructure**
   - ``msTools``

2. **Bottom-up semantic construction**
   - ``msCodeID``
   - ``find_mscodeids``

3. **Movement and gait detection**
   - ``msGait``
   - ``find_gait``

4. **Validation and supporting utilities**
   - ``tests`` and auxiliary scripts outside the main package structure

Pipeline view
-------------

.. graphviz::
   :caption: Repository module relationships
   :align: center

   digraph repo_modules {
      rankdir=LR;
      graph [fontname="Helvetica"];
      node  [shape=box, fontname="Helvetica"];
      edge  [fontname="Helvetica"];

      msTools         [label="msTools\n(shared infrastructure)"];
      msCodeID        [label="msCodeID\n(bottom-up semantic construction)"];
      find_mscodeids  [label="find_mscodeids\nCLI"];
      msGait          [label="msGait\nmovement and gait detection)"];
      find_gait       [label="find_gait\nCLI"];
      tests           [label="tests\nvalidation utilities"];

      msTools -> msCodeID;
      msTools -> msGait;
      msCodeID -> find_mscodeids;
      msGait -> find_gait;
      find_mscodeids -> find_gait;
      find_gait -> tests;
   }

Module groups
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

Movement and gait detection
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. toctree::
   :maxdepth: 1

   msGait
   find_gait

How the pieces fit together
---------------------------

``msTools``
   Provides configuration loading, UTC normalization, internationalization,
   shared models, and PostgreSQL/InfluxDB access.

``msCodeID``
   Implements the bottom-up construction of semantic activity windows from raw
   wearable references.

``find_mscodeids``
   Runs the first executable pipeline stage and stores ``activity_leg`` and
   ``activity_all``.

``msGait``
   Implements inertial movement detection, bilateral gait derivation, and GPS
   enrichment.

``find_gait``
   Runs the second executable pipeline stage and stores
   ``effective_movement`` and ``effective_gait``.

``tests``
   Contains empirical validation utilities based on manually labeled
   ground-truth windows.

Notes
-----

The repository is intentionally structured so that semantic construction and
gait detection are separated into two stages:

- a first stage that builds semantic candidate windows from raw wearable data
- a second stage that performs inertial analysis and gait validation on those
  previously built windows