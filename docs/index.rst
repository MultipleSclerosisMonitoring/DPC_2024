.. MS Monitoring documentation master file

MS Monitoring Documentation
===========================

Welcome to the **MS Monitoring** documentation.

This documentation describes the repository structure, the command-line tools,
the shared utility layer, and the movement and gait detection pipeline used in
the project.

Project overview
----------------

The repository is organized around two main processing stages:

1. **Bottom-up semantic construction**
   - retrieval of distinct CodeIDs from InfluxDB
   - construction of `activity_leg`
   - construction of bilateral `activity_all`

2. **Movement and gait detection**
   - retrieval of `activity_all`
   - leg-level inertial processing
   - detection of `effective_movement`
   - derivation of `effective_gait`
   - GPS-based enrichment of gait intervals

High-Level Workflow
-------------------

.. graphviz::
   :caption: High-level pipeline overview
   :align: center

   digraph overview {
      rankdir=LR;
      graph [fontname="Helvetica"];
      node  [shape=box, fontname="Helvetica"];
      edge  [fontname="Helvetica"];

      FindMSCodeIDs   [label="find_mscodeids CLI"];
      ActivityLeg     [label="activity_leg"];
      ActivityAll     [label="activity_all"];
      FindGait        [label="find_gait CLI"];
      EffectiveMove   [label="effective_movement"];
      EffectiveGait   [label="effective_gait\n(+ GPS validation)"];

      FindMSCodeIDs -> ActivityLeg -> ActivityAll -> FindGait -> EffectiveMove -> EffectiveGait;
   }

Contents
--------

.. toctree::
   :maxdepth: 2
   :caption: Sections

   usage
   modules

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`