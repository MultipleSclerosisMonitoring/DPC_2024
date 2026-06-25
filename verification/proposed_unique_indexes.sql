-- Proposed uniqueness constraints for the semantic tables.
--
-- This file is intentionally NOT applied automatically.
-- It captures the current recommendation after reviewing the repository's
-- runtime semantics and the idempotency checks implemented in DataManager.
--
-- Summary
-- -------
-- Safe now:
--   1. effective_movement(codeid_id, leg, start_time, end_time)
--   2. effective_gait(codeid_id, start_time, end_time)
--
-- Optional later:
--   3. activity_leg(codeid_id, foot, start_time, end_time)
--
-- Not recommended for now:
--   - activity_all
--
-- Rationale
-- ---------
-- effective_movement:
--   One row represents one effective movement episode for one leg inside one
--   CodeID/session. duration is derivable from start_time/end_time, so it is
--   descriptive rather than part of the natural key.
--
-- effective_gait:
--   One row represents one bilateral gait interval for one CodeID/session.
--   gait_confidence_level and GPS fields are enrichments that may be updated
--   after the base interval already exists, so they should not participate in
--   the uniqueness key.
--
-- activity_leg:
--   This is a plausible natural key if the segmentation algorithm is assumed
--   stable. If segmentation rules are still evolving, keep this as an
--   application-level idempotency check only.
--
-- activity_all:
--   Not recommended yet because its rows depend on array-valued references and
--   on the exact reconstruction of activity_leg identifiers.
--
-- Operational note
-- ----------------
-- Before applying any UNIQUE index in an existing database, verify that there
-- are no duplicates already present. Example checks are included below.
--
-- -------------------------------------------------------------------------
-- 0. Duplicate checks
-- -------------------------------------------------------------------------

-- effective_movement duplicates under the proposed key
SELECT codeid_id, leg, start_time, end_time, COUNT(*)
FROM effective_movement
GROUP BY codeid_id, leg, start_time, end_time
HAVING COUNT(*) > 1;

-- effective_gait duplicates under the proposed key
SELECT codeid_id, start_time, end_time, COUNT(*)
FROM effective_gait
GROUP BY codeid_id, start_time, end_time
HAVING COUNT(*) > 1;

-- activity_leg duplicates under the optional key
SELECT codeid_id, foot, start_time, end_time, COUNT(*)
FROM activity_leg
GROUP BY codeid_id, foot, start_time, end_time
HAVING COUNT(*) > 1;

-- -------------------------------------------------------------------------
-- 1. Safe indexes to apply now
-- -------------------------------------------------------------------------

CREATE UNIQUE INDEX IF NOT EXISTS uq_effective_movement_codeid_leg_interval
    ON effective_movement(codeid_id, leg, start_time, end_time);

CREATE UNIQUE INDEX IF NOT EXISTS uq_effective_gait_codeid_interval
    ON effective_gait(codeid_id, start_time, end_time);

-- -------------------------------------------------------------------------
-- 2. Optional index to apply only if activity_leg segmentation is considered
--    stable and should be database-enforced.
-- -------------------------------------------------------------------------

-- CREATE UNIQUE INDEX IF NOT EXISTS uq_activity_leg_codeid_foot_interval
--     ON activity_leg(codeid_id, foot, start_time, end_time);

-- -------------------------------------------------------------------------
-- 3. Explicitly not recommended for now
-- -------------------------------------------------------------------------

-- No UNIQUE index is proposed for activity_all at this time.
-- The row semantics still depend on array-valued references
-- (codeid_ids, codeleg_ids, macs, device_names, active_legs) and on how
-- activity_leg rows are reconstructed.
