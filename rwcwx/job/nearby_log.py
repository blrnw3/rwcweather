"""Periodic logger of nearby-station readings (temperature and today's rain).

Intended to be run from cron every 10 minutes via scripts/run_nearby_log.sh. It writes one row per
(station, observation time) into nearby_obs and drops rows older than 48 hours. Safe if the table
does not exist yet (logs a warning and exits 0). Does not query or write any other table.
"""
from datetime import datetime

from rwcwx import logger
from rwcwx.nearby import api as nearby_api, parse, store


def collect(now_utc=None):
    """Fetch current readings and return the rows to log (no DB)."""
    rows = []
    for st in parse.STATIONS:
        rec = parse.station_record(st, nearby_api._obs_for(st))
        if not rec.get("observed_at") or rec.get("temp_c") is None:
            continue
        rows.append(dict(station=rec["id"], t_obs=rec["observed_at"],
                         temp_c=rec["temp_c"], rain_today_mm=rec.get("rain_today_mm")))
    return rows


def run(now_utc=None) -> dict:
    now_utc = now_utc or datetime.utcnow()
    rows = collect()
    try:
        n = store.upsert_many(rows, now_utc=now_utc)
        pruned = store.prune(now_utc=now_utc)
    except store.TableMissing:
        logger.warning("nearby_obs table missing; skip log (apply data/migrations/20261111_nearby_obs.sql)")
        return dict(logged=0, pruned=0, fetched=len(rows), table=False)
    logger.info("nearby log: wrote %s rows, pruned %s (fetched %s)", n, pruned, len(rows))
    return dict(logged=n, pruned=pruned, fetched=len(rows), table=True)


if __name__ == "__main__":
    run()
