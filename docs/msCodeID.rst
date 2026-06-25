msCodeID package
================

The ``msCodeID`` package is responsible for the first semantic stage of the
pipeline. It retrieves raw wearable references from InfluxDB, builds per-leg
activity segments, and prepares the bilateral structures that are later stored
as ``activity_leg`` and ``activity_all`` in PostgreSQL.

Architecture overview
---------------------

.. graphviz::
   :caption: Bottom-up semantic construction
   :align: center

   digraph class_msCodeID {
      rankdir=TB;
      graph [fontname="Helvetica"];
      node  [shape=record, fontname="Helvetica"];
      edge  [fontname="Helvetica"];

      CodeIDProcessor [label="{CodeIDProcessor|
        + fetch_codeid_data(...)\l
        + identify_activity_segments(...)\l
        + build_activity_leg_frames(...)\l
        + inter_segs(...)\l
        + merge_activity_legs_to_all(...)\l
        + build_activity_all_frame(...)\l
        + save_to_postgresql(...)\l
      }"];

      Raw [label="{Raw inputs|CodeID\lFoot\lDeviceName\lMAC\l_time\l}"];
      ActivityLeg [label="{activity_leg|per-foot semantic windows}"];
      ActivityAll [label="{activity_all|bilateral candidate windows}"];

      Raw -> CodeIDProcessor;
      CodeIDProcessor -> ActivityLeg;
      CodeIDProcessor -> ActivityAll;
   }

Core component
--------------

``CodeIDProcessor`` (``msCodeID.codeid_processor``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This class performs the bottom-up construction of semantic activity windows.

Its main responsibilities are:

- retrieving CodeID-level wearable references from InfluxDB
- identifying contiguous activity segments for each foot separately
- building left/right frames compatible with ``activity_leg``
- computing bilateral temporal intersections
- building the merged structure later stored as ``activity_all``

Bottom-up semantic construction
-------------------------------

The package implements the first semantic layer of the project as follows:

1. retrieve raw wearable references for one ``CodeID`` from InfluxDB
2. keep the reference stream needed to delimit activity in time
3. split the data by foot (``Left`` / ``Right``)
4. group rows into contiguous segments according to temporal gaps and device
   changes
5. build left/right semantic frames compatible with ``activity_leg``
6. compute bilateral overlaps between left and right activity segments
7. merge those overlaps into a bilateral structure compatible with
   ``activity_all``

Why this stage matters
----------------------

``msCodeID`` is the module that makes the second stage possible. Without the
semantic candidate windows created here, the gait detector would need to scan
raw telemetry continuously instead of working on already localized episodes.

Notes
-----

- activity segmentation is gap-based
- zero-duration segments are filtered out before downstream processing
- bilateral activity is built through temporal intersection of left and right
  leg segments
- the outputs of this package are later consumed by ``msGait``

API reference
-------------

CodeID processor
~~~~~~~~~~~~~~~~

.. automodule:: msCodeID.codeid_processor
   :members:
   :undoc-members:
   :show-inheritance:
