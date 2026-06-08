msCodeID package
================

The ``msCodeID`` package is responsible for the first semantic stage of the
pipeline. It retrieves raw wearable references from InfluxDB, builds per-leg
activity segments, and prepares the bilateral structures that are later stored
as ``activity_leg`` and ``activity_all`` in PostgreSQL.

Architecture Overview
---------------------

.. graphviz::
   :caption: CodeIDProcessor and bottom-up semantic construction
   :align: center

   digraph class_msCodeID {
      rankdir=TB;
      graph [fontname="Helvetica"];
      node  [shape=record, fontname="Helvetica"];
      edge  [fontname="Helvetica"];

      CodeIDProcessor [label="{CodeIDProcessor|
        + __init__(data_manager, verbose)\l
        + fetch_codeid_data(codeid, start_datetime, end_datetime)\l
        + identify_activity_segments(df, threshold_seconds, foot)\l
        + build_activity_leg_frames(sensor_data, codeid_id, gap_threshold_seconds)\l
        + build_activity_all_frame(activity_seg_right_merge, activity_seg_left_merge)\l
        + inter_segs(sg1, sg2)\l
        + merge_activity_legs_to_all(act_segR, act_segL, inter)\l
        + save_to_postgresql(table_name, df)\l
      }"];

      DataManager [label="{DataManager|
        + get_influx_client()\l
        + transform_activityleg()\l
        + store_data()\l
      }"];

      CodeIDProcessor -> DataManager;
   }

Core Components
---------------

``CodeIDProcessor`` (``msCodeID.codeid_processor``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This class performs the bottom-up construction of semantic activity windows.

Its main responsibilities are:

- retrieving CodeID-level wearable references from InfluxDB
- identifying contiguous activity segments for each foot separately
- building left/right frames compatible with ``activity_leg``
- computing bilateral temporal intersections
- building the merged structure later stored as ``activity_all``

Important public methods include:

- ``__init__(data_manager: DataManager, verbose: int = 0) -> None``
- ``fetch_codeid_data(codeid: str, start_datetime: datetime, end_datetime: datetime) -> pandas.DataFrame``
- ``identify_activity_segments(df: pandas.DataFrame, threshold_seconds: float = 70, foot: str = "Left") -> pandas.DataFrame``
- ``build_activity_leg_frames(sensor_data: pandas.DataFrame, codeid_id: int, gap_threshold_seconds: float = 80.0) -> tuple[pandas.DataFrame, pandas.DataFrame, pandas.DataFrame, pandas.DataFrame]``
- ``build_activity_all_frame(activity_seg_right_merge: pandas.DataFrame, activity_seg_left_merge: pandas.DataFrame) -> pandas.DataFrame``
- ``inter_segs(sg1: pandas.DataFrame, sg2: pandas.DataFrame) -> pandas.DataFrame``
- ``merge_activity_legs_to_all(act_segR: pandas.DataFrame, act_segL: pandas.DataFrame, inter: pandas.DataFrame) -> pandas.DataFrame``
- ``save_to_postgresql(table_name: str, df: pandas.DataFrame) -> None``

Bottom-up semantic construction
-------------------------------

The package implements the first semantic layer of the project as follows:

1. Retrieve raw wearable references for one ``CodeID`` from InfluxDB.
2. Keep the reference stream needed to delimit activity in time.
3. Split the data by foot (``Left`` / ``Right``).
4. Group rows into contiguous segments according to temporal gaps and device changes.
5. Build left/right semantic frames compatible with ``activity_leg``.
6. Compute bilateral overlaps between left and right activity segments.
7. Merge those overlaps into a bilateral structure compatible with ``activity_all``.

This means the repository now includes the missing bottom-up stage that
constructs ``activity_leg`` and ``activity_all`` before the gait-detection
stage starts.

Notes
-----

- Activity segmentation is gap-based.
- Zero-duration segments are filtered out before downstream processing.
- Bilateral activity is built through temporal intersection of left and right
  leg segments.
- The outputs of this package are later consumed by ``msGait``.

API Reference
-------------

CodeID processor
~~~~~~~~~~~~~~~~

.. automodule:: msCodeID.codeid_processor
   :members:
   :undoc-members:
   :show-inheritance: