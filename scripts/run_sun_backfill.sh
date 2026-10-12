#!/usr/bin/env bash
# Wrapper for rwcwx/job/sun_backfill.py: one resumable chunk per run, single instance, idle priority, capped memory.
# Not in cron until approved; suggested nightly (02:30 PT = 09:30 UTC):
#   30 9 * * * /home/ben/rwcweather/scripts/run_sun_backfill.sh
# Extra args are passed through, e.g. --dry-run --start 2022-06-01 --end 2022-08-31 --csv /tmp/bf.csv
# Overridable: RWCWX_ROOT, RWCWX_ENV_FILE, RWCWX_VENV, LOG_DIR, SUN_MEM_KB, BACKFILL_TIMEOUT.
set -euo pipefail

ROOT="${RWCWX_ROOT:-/home/ben/rwcweather}"
ENV_FILE="${RWCWX_ENV_FILE:-/etc/rwcwx.env}"
VENV="${RWCWX_VENV:-$ROOT/venv_prod}"
LOG_DIR="${LOG_DIR:-$ROOT/log}"
LOCK="${SUN_BACKFILL_LOCK:-/tmp/rwcwx_sun_backfill.lock}"
MEM_KB="${SUN_MEM_KB:-600000}"
TIMEOUT="${BACKFILL_TIMEOUT:-1800}"

mkdir -p "$LOG_DIR"
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "$(date -u +%FT%TZ) previous sun_backfill still running; skipping" >> "$LOG_DIR/sun_backfill.log"
    exit 0
fi

cd "$ROOT"
set -a; . "$ENV_FILE"; set +a                       # MYSQL_URL
export PYTHONPATH="$ROOT" OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TZ=UTC
ulimit -v "$MEM_KB"
if [[ -f "$LOG_DIR/sun_backfill.log" && $(stat -c %s "$LOG_DIR/sun_backfill.log") -gt 5242880 ]]; then
    mv -f "$LOG_DIR/sun_backfill.log" "$LOG_DIR/sun_backfill.log.1"
fi
exec nice -n 19 ionice -c3 timeout "$TIMEOUT" "$VENV/bin/python" rwcwx/job/sun_backfill.py "$@" >> "$LOG_DIR/sun_backfill.log" 2>&1
