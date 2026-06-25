-- Reset derived semantic tables while preserving codeids.
--
-- Intended use:
--   Rebuild activity_leg, activity_all, effective_movement, and effective_gait
--   from the current pipeline implementation without losing the source CodeID
--   inventory.
--
-- Notes:
--   - codeids is intentionally preserved.
--   - RESTART IDENTITY resets the SERIAL sequences of the truncated tables.
--   - CASCADE is not used here because the truncation order already respects
--     the foreign-key dependencies among the derived tables.

BEGIN;

TRUNCATE TABLE
    activity_all,
    activity_leg,
    effective_movement,
    effective_gait
RESTART IDENTITY;

COMMIT;
