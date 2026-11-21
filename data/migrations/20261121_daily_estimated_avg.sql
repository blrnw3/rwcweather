-- Add type 'avg' (daily mean temperature) to daily_estimated.
-- Existing Tmax, Tmin and rain rows are unchanged. Idempotent if already applied
-- (MySQL allows repeating the same ENUM definition).
-- Do NOT apply this file or load rows as part of a dry run. Apply only with
-- explicit approval, after reviewing the generated mean CSV:
--   mysql wx < data/migrations/20261121_daily_estimated_avg.sql
--   mysql wx < path/to/daily_estimated_mean_v5.sql
ALTER TABLE `daily_estimated`
  MODIFY `type` enum('max','min','total','avg') NOT NULL
  COMMENT 'Tmax, Tmin, rain total, or daily mean temperature';
