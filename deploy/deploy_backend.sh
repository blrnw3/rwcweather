#!/usr/bin/env bash
# Remote paths below intentionally expand on the client before being sent to SSH.
# shellcheck disable=SC2029

set -euo pipefail

DRY_RUN=false
INSTALL_DEPS=false

usage() {
    echo "Usage: $0 [--dry-run] [--install-deps]" >&2
}

while (($#)); do
    case "$1" in
        --dry-run) DRY_RUN=true ;;
        --install-deps) INSTALL_DEPS=true ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage
            exit 2
            ;;
    esac
    shift
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DEPLOY_HOST="${RWCWX_DEPLOY_HOST:-ben@138.68.56.237}"
DEPLOY_PORT="${RWCWX_DEPLOY_PORT:-8294}"
REMOTE_ROOT="${RWCWX_REMOTE_ROOT:-/home/ben/rwcweather}"
PUBLIC_URL="${RWCWX_PUBLIC_URL:-https://rwcweather.com}"
SERVICE_NAME="${RWCWX_BACKEND_SERVICE:-rwcwx}"
REMOTE_ENV_FILE="${RWCWX_REMOTE_ENV_FILE:-/etc/rwcwx.env}"
REMOTE_PYTHON="$REMOTE_ROOT/venv_prod/bin/python"
REMOTE_PIP="$REMOTE_ROOT/venv_prod/bin/pip"

for command in python3 rsync ssh; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Required command not found: $command" >&2
        exit 1
    fi
done

SSH_ARGS=(-p "$DEPLOY_PORT" -o BatchMode=yes -o ConnectTimeout=10)
RSYNC_SSH="ssh -p $DEPLOY_PORT -o BatchMode=yes -o ConnectTimeout=10"
RSYNC_ARGS=(-rlptv --exclude=__pycache__/ --exclude='*.pyc')
if [[ "$DRY_RUN" == true ]]; then
    RSYNC_ARGS+=(--dry-run)
fi

echo "Checking local backend syntax..."
python3 - "$REPO_ROOT" <<'PY'
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
files = list((root / "rwcwx").rglob("*.py")) + [root / "wsgi.py"]
for path in files:
    compile(path.read_bytes(), str(path), "exec")
print(f"Compiled {len(files)} Python files")
PY

echo "Checking production access and runtime..."
ssh "${SSH_ARGS[@]}" "$DEPLOY_HOST" \
    "test -x '$REMOTE_PYTHON' && test -d '$REMOTE_ROOT/rwcwx' && test -d '$REMOTE_ROOT/deploy'"

local_requirements_hash="$(python3 -c \
    'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' \
    "$REPO_ROOT/requirements.txt")"
remote_requirements_hash="$(ssh "${SSH_ARGS[@]}" "$DEPLOY_HOST" \
    "'$REMOTE_PYTHON' -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], \"rb\").read()).hexdigest())' '$REMOTE_ROOT/requirements.txt'")"

if [[ "$local_requirements_hash" != "$remote_requirements_hash" ]]; then
    if [[ "$INSTALL_DEPS" != true ]]; then
        if [[ "$DRY_RUN" == true ]]; then
            echo "requirements.txt differs; a real deployment will require --install-deps."
        else
            echo "requirements.txt differs from production." >&2
            echo "Rerun with --install-deps after reviewing the dependency changes." >&2
            exit 1
        fi
    fi
else
    echo "Backend dependencies are unchanged."
fi

echo "Syncing backend package..."
rsync "${RSYNC_ARGS[@]}" -e "$RSYNC_SSH" \
    "$REPO_ROOT/rwcwx/" "$DEPLOY_HOST:$REMOTE_ROOT/rwcwx/"

echo "Syncing backend entrypoint and requirements..."
rsync "${RSYNC_ARGS[@]}" -e "$RSYNC_SSH" \
    "$REPO_ROOT/wsgi.py" "$REPO_ROOT/requirements.txt" \
    "$DEPLOY_HOST:$REMOTE_ROOT/"

echo "Syncing uWSGI configuration..."
rsync "${RSYNC_ARGS[@]}" -e "$RSYNC_SSH" \
    "$REPO_ROOT/deploy/rwcwx.ini" "$DEPLOY_HOST:$REMOTE_ROOT/deploy/"

if [[ "$DRY_RUN" == true ]]; then
    echo "Dry run complete; production was not changed or restarted."
    exit 0
fi

if [[ "$INSTALL_DEPS" == true ]]; then
    echo "Installing backend dependencies..."
    ssh "${SSH_ARGS[@]}" "$DEPLOY_HOST" \
        "'$REMOTE_PIP' install -r '$REMOTE_ROOT/requirements.txt'"
fi

echo "Validating uploaded backend with the production runtime..."
ssh "${SSH_ARGS[@]}" "$DEPLOY_HOST" \
    "cd '$REMOTE_ROOT' && '$REMOTE_PYTHON' -m compileall -q rwcwx wsgi.py"
ssh "${SSH_ARGS[@]}" "$DEPLOY_HOST" \
    "set -a; . '$REMOTE_ENV_FILE'; set +a; cd '$REMOTE_ROOT'; '$REMOTE_PYTHON' -c 'import wsgi; assert wsgi.app'"

echo "Gracefully reloading $SERVICE_NAME..."
ssh "${SSH_ARGS[@]}" "$DEPLOY_HOST" \
    "main_pid=\$(systemctl show '$SERVICE_NAME' --property=MainPID --value); \
     test \"\$main_pid\" -gt 1; \
     kill -HUP \"\$main_pid\"; \
     sleep 2; \
     systemctl is-active --quiet '$SERVICE_NAME'; \
     kill -0 \"\$main_pid\"; \
     systemctl status '$SERVICE_NAME' --no-pager"

echo "Verifying production backend..."
RWCWX_PUBLIC_URL="$PUBLIC_URL" "$SCRIPT_DIR/verify_backend.sh"

echo "Backend deployment complete: $PUBLIC_URL/api/web/dashboard/live"
