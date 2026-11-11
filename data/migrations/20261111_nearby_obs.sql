-- Nearby-station observation log (rwcwx/nearby) used to compute today's high and low when a feed
-- does not publish them (Tum Suden, White Oaks). Also fills in if another station's published range is missing.
-- One row per (station, observation time). Rows older than 2 days are pruned by the logger.
-- Creates a new table only; no existing table is touched. Idempotent.
-- Apply BEFORE (or right after) deploying the backend, with approval for this specific write:
--   mysql wx < data/migrations/20261111_nearby_obs.sql
-- Until the table exists the API still works (published Lo-Hi are shown; others stay a dash)
-- and the logger exits 0 after logging that the table is missing.
CREATE TABLE IF NOT EXISTS `nearby_obs` (
  `station` varchar(32) NOT NULL COMMENT 'stable id: pulgas, sfo, tum_suden, white_oaks, jasper_ridge',
  `t_obs` datetime NOT NULL COMMENT 'UTC observation time from the source (dedupe key with station)',
  `temp_c` decimal(5,2) DEFAULT NULL COMMENT 'air temperature, Celsius',
  `rain_today_mm` decimal(6,3) DEFAULT NULL COMMENT 'source daily rainfall at t_obs, millimetres',
  `t_log` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'UTC, when this row was last written',
  PRIMARY KEY (`station`, `t_obs`),
  KEY `t_obs_key` (`t_obs`)
) ENGINE=InnoDB
DEFAULT CHARSET utf8mb4
COMMENT 'Short-lived log of nearby-station readings for daily temperature range';
