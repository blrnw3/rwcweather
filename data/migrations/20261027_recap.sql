-- Written weather recaps shown on the home page (rwcwx/recap, POST /api/recap, GET /api/recap/latest).
-- One row per (kind, period): kind 'day' -> period 'YYYY-MM-DD'; 'month_to_date' and 'month' -> period 'YYYY-MM'.
-- Creates a new table only; no existing table is touched. Idempotent.
-- Apply BEFORE (or right after) deploying the backend; until it exists the GET answers "available": false
-- and the POST answers 503 (dry runs still work):
--   mysql wx < data/migrations/20261027_recap.sql
CREATE TABLE IF NOT EXISTS `recap` (
  `kind` varchar(16) NOT NULL COMMENT 'day, month_to_date or month',
  `period` varchar(10) NOT NULL COMMENT 'station-local (PT) period: YYYY-MM-DD for day, YYYY-MM for the month kinds',
  `body_md` text NOT NULL COMMENT 'markdown subset: paragraphs, - lists, **bold**, [links](https://...)',
  `generated_at` datetime NOT NULL COMMENT 'UTC time the writer generated the text',
  `t_mod` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'UTC, last written here',
  PRIMARY KEY (`kind`, `period`),
  KEY `t_mod_key` (`t_mod`)
) ENGINE=InnoDB
DEFAULT CHARSET utf8mb4
COMMENT 'Written daily / month-to-date / monthly weather recaps for the home page';
