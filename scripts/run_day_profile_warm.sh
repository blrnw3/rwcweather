#!/usr/bin/env bash
# Warm the Daily profile report's month caches (rwcwx.calc.day_profile): read-only on the DB, writes only the cache
# files ($ROOT/cache/day_profile). Finished months are kept 30 days, so most runs take ~1 s; on the day a batch
# expires (or after a deploy that changed the cache key) it rebuilds everything, ~2.5 min on prod.
#   Cron (ben's crontab, see deploy/crontab):  30 10 * * * /home/ben/rwcweather/scripts/run_day_profile_warm.sh
#   deploy/deploy_backend.sh also starts it in the background after the reload.
# Single instance (flock), low priority, capped run time. Overridable: RWCWX_ROOT, RWCWX_ENV_FILE, RWCWX_VENV,
# LOG_DIR, PROFILE_WARM_TIMEOUT.
set -euo pipefail

ROOT="${RWCWX_ROOT:-/home/ben/rwcweather}"
ENV_FILE="${RWCWX_ENV_FILE:-/etc/rwcwx.env}"
VENV="${RWCWX_VENV:-$ROOT/venv_prod}"
LOG_DIR="${LOG_DIR:-$ROOT/log}"
LOG="$LOG_DIR/day_profile_warm.log"
LOCK="${PROFILE_WARM_LOCK:-/tmp/rwcwx_day_profile_warm.lock}"
TIMEOUT="${PROFILE_WARM_TIMEOUT:-1200}"

mkdir -p "$LOG_DIR"
# rotate at ~1 MB, keep one old copy (each run logs one or two lines)
if [[ -f "$LOG" && $(stat -c %s "$LOG") -gt 1048576 ]]; then
    mv -f "$LOG" "$LOG.1"
fi
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "$(date -u +%FT%TZ) previous day profile warm-up still running; skipping" >> "$LOG"
    exit 0
fi

cd "$ROOT"
set -a; . "$ENV_FILE"; set +a                       # MYSQL_URL
export PYTHONPATH="$ROOT"
echo "$(date -u +%FT%TZ) start" >> "$LOG"
status=0
nice -n 15 ionice -c3 timeout "$TIMEOUT" "$VENV/bin/python" -W ignore -m rwcwx.calc.day_profile "$@" >> "$LOG" 2>&1 || status=$?
echo "$(date -u +%FT%TZ) exit $status" >> "$LOG"
exit $status
