-- One-off cleanup after deploying "only write minutes up to now": the first sun_classify version (#16) wrote
-- placeholder rows for every daylight minute of the day, including minutes that had not happened yet
-- (value NULL, flags 'missing'). Run once AFTER the new code is deployed. Only touches live, unclassified,
-- 'missing'-only rows in the future; real data and manual rows are untouched.
SELECT COUNT(*) AS future_rows FROM obs_inferred
 WHERE kind = 'sunny' AND source = 'live' AND t >= UTC_TIMESTAMP() AND value IS NULL AND flags = 'missing';
DELETE FROM obs_inferred
 WHERE kind = 'sunny' AND source = 'live' AND t >= UTC_TIMESTAMP() AND value IS NULL AND flags = 'missing';
