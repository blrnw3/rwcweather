#!/usr/bin/env bash
# Cron wrapper for rwcwx/job/nearby_log.py: single instance (flock), low priority.
# Suggested crontab (install at ship time; do not put secrets here):
#   */10 * * * * /home/ben/rwcweather/scripts/run_nearby_log.sh
# Overridable: RWCWX_ROOT, RWCWX_ENV_FILE, RWCWX_VENV, LOG_DIR.
set -euo pipefail

ROOT="${RWCWX_ROOT:-/home/ben/rwcweather}"
ENV_FILE="${RWCWX_ENV_FILE:-/etc/rwcwx.env}"
VENV="${RWCWX_VENV:-$ROOT/venv_prod}"
LOG_DIR="${LOG_DIR:-$ROOT/log}"
LOCK="${NEARBY_LOG_LOCK:-/tmp/rwcwx_nearby_log.lock}"

mkdir -p "$LOG_DIR"
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "$(date -u +%FT%TZ) previous nearby_log still running; skipping" >> "$LOG_DIR/nearby_log.log"
    exit 0
fi

cd "$ROOT"
set -a; . "$ENV_FILE"; set +a
export PYTHONPATH="$ROOT"
# rotate at ~1 MB, keep one old copy
if [[ -f "$LOG_DIR/nearby_log.log" && $(stat -c %s "$LOG_DIR/nearby_log.log") -gt 1048576 ]]; then
    mv -f "$LOG_DIR/nearby_log.log" "$LOG_DIR/nearby_log.log.1"
fi
exec nice -n 15 ionice -c3 timeout 180 "$VENV/bin/python" -m rwcwx.job.nearby_log >> "$LOG_DIR/nearby_log.log" 2>&1
