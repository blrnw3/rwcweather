-- obs_inferred.source: enum -> varchar so API estimates can be labelled 'api:<name>' (e.g. 'api:hrrr+asos').
-- Existing values ('live', 'backfill', 'manual') are kept as-is. Apply before running rwcwx/job/sun_api_backfill.py:
--   mysql wx < data/migrations/20261013_obs_inferred_source_varchar.sql
ALTER TABLE `obs_inferred`
  MODIFY `source` varchar(24) NOT NULL DEFAULT 'live' COMMENT 'live, backfill, manual, or api:<name>; manual rows are never overwritten';
