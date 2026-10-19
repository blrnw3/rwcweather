#!/usr/bin/env bash
# Cron wrapper for rwcwx/job/sun_classify.py: single instance (flock), low priority, capped memory.
#   */5 * * * * /home/ben/rwcweather/scripts/run_sun_classify.sh
# Extra args are passed through (e.g. --dry-run, -d 2026-10-09). Overridable: RWCWX_ROOT, RWCWX_ENV_FILE, RWCWX_VENV,
# LOG_DIR, SUN_MEM_KB.
set -euo pipefail

ROOT="${RWCWX_ROOT:-/home/ben/rwcweather}"
ENV_FILE="${RWCWX_ENV_FILE:-/etc/rwcwx.env}"
VENV="${RWCWX_VENV:-$ROOT/venv_prod}"
LOG_DIR="${LOG_DIR:-$ROOT/log}"
LOCK="${SUN_LOCK:-/tmp/rwcwx_sun_classify.lock}"
MEM_KB="${SUN_MEM_KB:-600000}"     # virtual memory cap; the job peaks ~60 MB RSS

mkdir -p "$LOG_DIR"
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "$(date -u +%FT%TZ) previous sun_classify still running; skipping" >> "$LOG_DIR/sun_classify.log"
    exit 0
fi

cd "$ROOT"
set -a; . "$ENV_FILE"; set +a                       # MYSQL_URL
export PYTHONPATH="$ROOT" OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
ulimit -v "$MEM_KB"
# rotate at ~5 MB, keep one old copy
if [[ -f "$LOG_DIR/sun_classify.log" && $(stat -c %s "$LOG_DIR/sun_classify.log") -gt 5242880 ]]; then
    mv -f "$LOG_DIR/sun_classify.log" "$LOG_DIR/sun_classify.log.1"
fi
exec nice -n 15 ionice -c3 timeout 600 "$VENV/bin/python" rwcwx/job/sun_classify.py "$@" >> "$LOG_DIR/sun_classify.log" 2>&1
