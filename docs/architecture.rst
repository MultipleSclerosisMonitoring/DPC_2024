Architecture
============

This page provides the system-level context for the repository. The individual
package pages describe APIs, but this section explains the architectural intent,
the domain model, and the relation between raw telemetry, semantic events, and
post-hoc clinical interpretation.

Architectural position
----------------------

The repository should not be understood as a black-box gait classifier or as a
finished clinical gait assessment tool. Its role is narrower and, in some
respects, more foundational:

- preserve raw wearable telemetry unchanged in a time-series store
- derive transparent, time-bounded semantic events from those raw signals
- persist the semantic events in a relational model that supports auditability,
  traceability, and longitudinal analysis
- allow later compatibility checks against clinical tests without forcing the
  blind processing stages to depend on test labels

This framing follows the digital-health perspective emphasized in the attached
paper: clinicians reason about episodes, durations, trends, asymmetry, and
changes over time rather than about isolated inertial samples.

Use-case view
-------------

.. graphviz::
   :caption: Primary use-case view
   :align: center

   digraph use_case_diagram {
      rankdir=LR;
      graph [fontname="Helvetica"];
      node [fontname="Helvetica"];

      subgraph cluster_system {
         label="MS Monitoring semantic pipeline";
         style=rounded;
         RawStore   [shape=ellipse, label="Preserve raw telemetry"];
         Semantic   [shape=ellipse, label="Derive semantic event layers"];
         Persist    [shape=ellipse, label="Persist semantic outputs"];
         Longitudinal [shape=ellipse, label="Support longitudinal review"];
         Compatibility [shape=ellipse, label="Check compatibility with\nstandardized test intervals"];
         Traceability [shape=ellipse, label="Trace semantic outputs\nback to raw ranges"];
      }

      Clinician [shape=box, style=rounded, label="Clinician / researcher"];
      Operator [shape=box, style=rounded, label="Pipeline operator"];
      DataEngineer [shape=box, style=rounded, label="Data engineer"];

      Operator -> RawStore;
      Operator -> Semantic;
      Operator -> Persist;
      Clinician -> Longitudinal;
      Clinician -> Compatibility;
      DataEngineer -> Traceability;
   }

Core components
---------------

.. graphviz::
   :caption: Component diagram
   :align: center

   digraph component_diagram {
      rankdir=LR;
      graph [fontname="Helvetica"];
      node  [shape=box, fontname="Helvetica", style="rounded"];
      edge  [fontname="Helvetica"];

      Sensors    [label="Wearable sensors\nsmart socks"];
      MobileApp  [label="Mobile app gateway\nHealthyWear-like collector"];
      Influx     [label="InfluxDB\nraw immutable telemetry"];
      Postgres   [label="PostgreSQL\nsemantic tables"];
      Tools      [label="msTools\nshared infrastructure"];
      CodeID     [label="msCodeID\nsemantic construction"];
      Gait       [label="msGait\ninertial movement + graded gait"];
      CLI1       [label="find_mscodeids"];
      CLI2       [label="find_gait"];
      Reporting  [label="tests + verification\nvalidation and reporting"];

      Sensors -> MobileApp -> Influx;
      Tools -> CodeID;
      Tools -> Gait;
      CodeID -> CLI1;
      Gait -> CLI2;
      CLI1 -> Postgres;
      CLI2 -> Postgres;
      Postgres -> Reporting;
      Influx -> Reporting;
   }

Hierarchical monitoring organization
------------------------------------

One useful idea from the paper is that monitoring data should be read as a
hierarchy, not as a flat bag of samples. The repository already implements most
of that hierarchy implicitly, even if some higher levels live outside the core
schema.

.. graphviz::
   :caption: Hierarchical organization of monitoring data and semantic layers
   :align: center

   digraph hierarchy_diagram {
      rankdir=TB;
      graph [fontname="Helvetica"];
      node  [shape=box, fontname="Helvetica", style="rounded"];
      edge  [fontname="Helvetica"];

      Subject  [label="Monitored subject\n(conceptual)"];
      Day      [label="Monitoring day\n(conceptual)"];
      Session  [label="Session / CodeID\n(maximal contiguous acquisition)"];
      LegAct   [label="activity_leg\nleg-level activity episode"];
      PersonAct [label="activity_all\nperson-level candidate activity"];
      EffMove  [label="effective_movement\nfiltered meaningful movement"];
      EffGait  [label="effective_gait\nbrief or robust bilateral gait"];
      TestAnn  [label="Clinical test interval\n(post-hoc annotation layer)"];

      Subject -> Day -> Session -> LegAct -> PersonAct -> EffMove -> EffGait;
      EffGait -> TestAnn [style=dashed, label="temporal alignment"];
   }

Domain model
------------

.. graphviz::
   :caption: Semantic data model
   :align: center

   digraph class_diagram {
      rankdir=LR;
      graph [fontname="Helvetica"];
      node  [shape=record, fontname="Helvetica"];
      edge  [fontname="Helvetica"];

      CodeID [label="{codeids|id\lcodeid\l}"];
      ActivityLeg [label="{activity_leg|id\lcodeid_id\lfoot\lstart_time\lend_time\lduration\l}"];
      ActivityAll [label="{activity_all|id\lcodeid_ids[]\lcodeleg_ids[]\lstart_time\lend_time\lduration\lactive_legs[]\l}"];
      EffectiveMovement [label="{effective_movement|id\lcodeid_id\lleg\lstart_time\lend_time\lduration\l}"];
      EffectiveGait [label="{effective_gait|id\lcodeid_id\lstart_time\lend_time\lduration\lgait_confidence_level\lgps_*\l}"];
      ClinicalTest [label="{clinical test interval|test_name\lstart\lend\l(external/reporting layer)\l}"];

      CodeID -> ActivityLeg;
      ActivityLeg -> ActivityAll;
      CodeID -> EffectiveMovement;
      CodeID -> EffectiveGait;
      ActivityAll -> EffectiveMovement [label="candidate window source"];
      EffectiveMovement -> EffectiveGait [label="left/right overlap"];
      EffectiveGait -> ClinicalTest [style=dashed, label="post-hoc temporal match"];
   }

Processing sequence
-------------------

.. graphviz::
   :caption: Conceptual processing sequence
   :align: center

   digraph sequence_diagram {
      rankdir=LR;
      graph [fontname="Helvetica"];
      node  [shape=box, fontname="Helvetica"];
      edge  [fontname="Helvetica"];

      User      [label="Operator"];
      CLI1      [label="find_mscodeids"];
      DM        [label="DataManager"];
      Influx    [label="InfluxDB"];
      PG        [label="PostgreSQL"];
      Processor [label="CodeIDProcessor"];
      CLI2      [label="find_gait"];
      Detector  [label="MovementDetector"];
      Report    [label="Compatibility report"];

      User -> CLI1 [label="run semantic stage"];
      CLI1 -> DM [label="load config / connect"];
      CLI1 -> Influx [label="discover CodeIDs + fetch raw references"];
      CLI1 -> Processor [label="segment per-foot activity"];
      Processor -> PG [label="store codeids, activity_leg, activity_all"];

      User -> CLI2 [label="run movement/gait stage"];
      CLI2 -> DM [label="load candidate activity_all windows"];
      CLI2 -> Detector [label="expand windows per leg"];
      Detector -> Influx [label="fetch inertial + GPS data"];
      Detector -> Detector [label="detect effective_movement"];
      Detector -> Detector [label="derive bilateral gait confidence"];
      Detector -> PG [label="store effective_movement/effective_gait"];

      User -> Report [label="compare against test inventory"];
      Report -> PG [label="read semantic outputs"];
   }

Confidence model
----------------

.. graphviz::
   :caption: Gait confidence levels
   :align: center

   digraph confidence_diagram {
      rankdir=TB;
      graph [fontname="Helvetica"];
      node  [shape=box, fontname="Helvetica", style="rounded"];
      edge  [fontname="Helvetica"];

      Start   [label="bilateral overlap detected"];
      None    [label="level 0\nno reported gait row\noverlap below brief threshold"];
      Brief   [label="level 1\nbrief bilateral gait\nuseful for short episodes"];
      Robust  [label="level 2\nrobust gait\noverlap >= min_gait_duration_sec"];

      Start -> None   [label="too short"];
      Start -> Brief  [label="meaningful but short"];
      Start -> Robust [label="strong evidence"];
   }

Raw-to-semantic lifecycle
-------------------------

.. graphviz::
   :caption: Activity diagram of the data lifecycle
   :align: center

   digraph activity_diagram {
      rankdir=LR;
      graph [fontname="Helvetica"];
      node [shape=box, fontname="Helvetica", style="rounded"];
      edge [fontname="Helvetica"];

      Raw        [label="raw telemetry"];
      Discover   [label="discover CodeIDs"];
      Segment    [label="segment left/right activity"];
      Intersect  [label="intersect both legs"];
      Candidate  [label="candidate bilateral windows"];
      Inertial   [label="inertial movement detection"];
      Overlap    [label="bilateral overlap analysis"];
      GPS        [label="GPS enrichment"];
      Report     [label="post-hoc compatibility report"];

      Raw -> Discover -> Segment -> Intersect -> Candidate -> Inertial -> Overlap -> GPS -> Report;
   }

Ontology-ready interpretation
-----------------------------

The paper also motivates an ontology-friendly reading of the repository. Even
though the implementation is relational, the semantic event tables already
behave like ontology classes linked by temporal relations:

- subjects/sessions are linked to semantic episodes
- episodes are explicitly time-bounded
- higher semantic layers are derived from lower ones
- clinical tests can be attached as another temporal annotation layer

This means the repository is already close to ontology-based data access in
spirit, even when queries are currently expressed over PostgreSQL tables.

Clinical tests as annotations, not primary labels
-------------------------------------------------

.. graphviz::
   :caption: Standardized clinical tests as a higher semantic annotation layer
   :align: center

   digraph clinical_annotation_diagram {
      rankdir=LR;
      graph [fontname="Helvetica"];
      node [shape=box, fontname="Helvetica", style="rounded"];
      edge [fontname="Helvetica"];

      Session  [label="Monitoring session / CodeID"];
      FreeLiving [label="Free-living semantic events\nactivity_leg -> activity_all ->\neffective_movement -> effective_gait"];
      TestIntervals [label="Standardized clinical test intervals\nTUG / T25FW / 2MWT / 6MWT"];
      Report [label="Post-hoc compatibility report\nnone / brief / robust"];

      Session -> FreeLiving;
      Session -> TestIntervals;
      FreeLiving -> Report [label="semantic evidence"];
      TestIntervals -> Report [label="temporal annotations"];
   }

A particularly useful clarification from the paper is that standardized tests
such as TUG, T25FW, 2MWT, or 6MWT should be thought of as **annotated time
intervals aligned with the semantic event stream**, not as the primary way the
pipeline defines movement.

That is consistent with the repository design:

- semantic processing remains blind and reusable
- test intervals are applied later as a reporting layer
- the new ``brief`` versus ``robust`` gait distinction improves that later
  compatibility step without contaminating the blind core algorithm

Design summary
--------------

The repository should be understood as a semantic digital health pipeline,
rather than a single-purpose gait classifier. Its core abstractions are:

- **candidate bilateral windows** from ``activity_all``
- **per-leg inertial movement** from ``effective_movement``
- **graded bilateral gait evidence** from ``effective_gait``
- **optional clinical test annotations** aligned later in time

That framing matches both the implementation and the paper’s rationale for
transparent, auditable, and longitudinally interpretable digital health
monitoring.
