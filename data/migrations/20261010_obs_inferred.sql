-- Inferred / classifier observations (e.g. sunshine from the webcam). Generic: one row per (kind, period start).
-- Apply: mysql wx < data/migrations/20261010_obs_inferred.sql   (idempotent; creates only, touches no existing table)
CREATE TABLE IF NOT EXISTS `obs_inferred` (
  `kind` varchar(16) NOT NULL COMMENT 'what was inferred, e.g. sunny',
  `t` datetime NOT NULL COMMENT 'UTC start of the period',
  `value` float DEFAULT NULL COMMENT 'inferred value (sunny: 1 = sun, 0 = no sun); NULL = not classified, see flags',
  `prob` decimal(4,3) DEFAULT NULL COMMENT 'model probability/confidence, if any',
  `minutes` smallint unsigned NOT NULL DEFAULT 1 COMMENT 'period length (1 live, e.g. 30 for backfill)',
  `source` enum('live', 'backfill', 'manual') NOT NULL DEFAULT 'live' COMMENT 'manual rows are never overwritten',
  `flags` varchar(64) DEFAULT NULL COMMENT 'comma list: missing, stale, ir, glitch, lowsun, ...',
  `model_version` varchar(32) DEFAULT NULL,
  `t_mod` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'last modified',
  PRIMARY KEY (`kind`, `t`),
  KEY `t_key` (`t`),
  KEY `t_mod_key` (`t_mod`)
) ENGINE=InnoDB
DEFAULT CHARSET utf8
COMMENT 'Inferred observations from classifiers (e.g. webcam sunshine), per kind and period';
