#!/usr/bin/env bash
# Start (or restart) the save_latest.py ingestion daemon on the production server, detached from the shell.
#
#   scripts/start_save_latest.sh            start; refuses if one is already running
#   scripts/start_save_latest.sh restart    SIGTERM the running one (SIGKILL after 10s), then start
#   scripts/start_save_latest.sh status     show the running process and the log tail
#
# Run as ben. Overridable: RWCWX_ROOT, RWCWX_ENV_FILE, RWCWX_VENV, OBS_PATH, EXTERNAL_ROOT, LOG_DIR,
# SAVE_LATEST_LOG / SAVE_LATEST_LOG_MAX_BYTES / SAVE_LATEST_LOG_BACKUPS (read by save_latest.py).
# The app logs to $LOG_DIR/save_latest.log (rotated 5 x 5 MB by save_latest.py itself). stdout/stderr go to
# $LOG_DIR/save_latest.out, which only catches output from before logging is set up (e.g. import errors).
set -euo pipefail

ROOT="${RWCWX_ROOT:-/home/ben/rwcweather}"
ENV_FILE="${RWCWX_ENV_FILE:-/etc/rwcwx.env}"
VENV="${RWCWX_VENV:-$ROOT/venv_prod}"
OBS_PATH="${OBS_PATH:-/var/www/rwc/html/cumulus/realtime.txt}"
EXTERNAL_ROOT="${EXTERNAL_ROOT:-out_prod}"
LOG_DIR="${LOG_DIR:-$ROOT/log}"
PATTERN="rwcwx/job/save_latest.py"

running_pids() { pgrep -u "$(id -u)" -f "^python3? $PATTERN" || true; }

status() {
    local pids; pids="$(running_pids)"
    if [[ -n "$pids" ]]; then ps -o pid,lstart,etime,cmd -p "${pids//$'\n'/,}"; else echo "save_latest.py is not running"; fi
    [[ -f "$LOG_DIR/save_latest.log" ]] && tail -n 5 "$LOG_DIR/save_latest.log"
    return 0
}

stop() {
    local pids pid
    pids="$(running_pids)"
    [[ -z "$pids" ]] && { echo "Nothing to stop"; return 0; }
    for pid in $pids; do
        echo "Sending SIGTERM to $pid: $(tr '\0' ' ' < "/proc/$pid/cmdline")"
        kill -TERM "$pid"
        for _ in $(seq 1 10); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
        if kill -0 "$pid" 2>/dev/null; then echo "Still running after 10s; sending SIGKILL to $pid"; kill -KILL "$pid"; sleep 1; fi
    done
}

start() {
    if [[ -n "$(running_pids)" ]]; then
        echo "save_latest.py is already running (use 'restart'):" >&2; status >&2; exit 1
    fi
    cd "$ROOT"
    set -a; . "$ENV_FILE"; set +a                       # MYSQL_URL
    export PYTHONPATH="$ROOT" VIRTUAL_ENV="$VENV" PATH="$VENV/bin:$PATH"
    mkdir -p "$LOG_DIR"
    export SAVE_LATEST_LOG="${SAVE_LATEST_LOG:-$LOG_DIR/save_latest.log}"
    setsid nohup python3 "$PATTERN" -o "$OBS_PATH" -e "$EXTERNAL_ROOT" \
        </dev/null >>"$LOG_DIR/save_latest.out" 2>&1 &
    local pid=$!
    sleep 3
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "save_latest.py exited immediately; see $LOG_DIR/save_latest.out and $SAVE_LATEST_LOG" >&2
        tail -n 20 "$LOG_DIR/save_latest.out" >&2 || true
        exit 1
    fi
    echo "Started save_latest.py as pid $pid (log: $SAVE_LATEST_LOG)"
    status
}

case "${1:-start}" in
    start) start ;;
    restart) stop; start ;;
    stop) stop ;;
    status) status ;;
    *) echo "Usage: $0 [start|restart|stop|status]" >&2; exit 2 ;;
esac
