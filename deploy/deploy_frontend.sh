#!/usr/bin/env bash
# Remote paths below intentionally expand on the client before being sent to SSH.
# shellcheck disable=SC2029

set -euo pipefail

DRY_RUN=false
case "${1:-}" in
    "") ;;
    --dry-run) DRY_RUN=true ;;
    *)
        echo "Usage: $0 [--dry-run]" >&2
        exit 2
        ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="$REPO_ROOT/web/app"

DEPLOY_HOST="${RWCWX_DEPLOY_HOST:-ben@138.68.56.237}"
DEPLOY_PORT="${RWCWX_DEPLOY_PORT:-8294}"
REMOTE_ROOT="${RWCWX_REMOTE_ROOT:-/home/ben/rwcweather}"
PUBLIC_URL="${RWCWX_PUBLIC_URL:-https://rwcweather.com}"
REMOTE_APP="$REMOTE_ROOT/web/app"
PROCESS_NAME="${RWCWX_FRONTEND_PROCESS:-rwcwx-app}"

for command in node npm rsync ssh; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Required command not found: $command" >&2
        exit 1
    fi
done

if [[ ! -d "$APP_DIR/node_modules" ]]; then
    echo "Frontend dependencies are missing." >&2
    echo "Run: cd web/app && npm install --no-package-lock --legacy-peer-deps" >&2
    exit 1
fi

SSH_ARGS=(-p "$DEPLOY_PORT" -o BatchMode=yes -o ConnectTimeout=10)
RSYNC_SSH="ssh -p $DEPLOY_PORT -o BatchMode=yes -o ConnectTimeout=10"
RSYNC_ARGS=(-rlptv)
if [[ "$DRY_RUN" == true ]]; then
    RSYNC_ARGS+=(--dry-run)
fi

echo "Checking production access and runtime..."
remote_next_version="$(ssh "${SSH_ARGS[@]}" "$DEPLOY_HOST" \
    "cd '$REMOTE_APP' && node -p \"require('next/package.json').version\"")"
local_next_version="$(cd "$APP_DIR" && node -p 'require("next/package.json").version')"

if [[ "$local_next_version" != "$remote_next_version" ]]; then
    echo "Next.js version mismatch: local=$local_next_version production=$remote_next_version" >&2
    echo "Build with the production version before deploying." >&2
    echo "For example: cd web/app && npm install --no-save --no-package-lock --legacy-peer-deps next@$remote_next_version" >&2
    exit 1
fi

echo "Building frontend with Next.js $local_next_version..."
node_major="$(node -p 'Number(process.versions.node.split(".")[0])')"
if (( node_major >= 17 )); then
    (cd "$APP_DIR" && NODE_OPTIONS="${NODE_OPTIONS:+$NODE_OPTIONS }--openssl-legacy-provider" npm run build)
else
    (cd "$APP_DIR" && npm run build)
fi

echo "Syncing frontend source..."
rsync "${RSYNC_ARGS[@]}" \
    --exclude=node_modules/ \
    --exclude=.next/ \
    --exclude=.env.development \
    --exclude=.env.local \
    --exclude=package.json \
    --exclude=package-lock.json \
    -e "$RSYNC_SSH" \
    "$APP_DIR/" "$DEPLOY_HOST:$REMOTE_APP/"

echo "Syncing compiled frontend..."
rsync "${RSYNC_ARGS[@]}" \
    --exclude=cache/ \
    -e "$RSYNC_SSH" \
    "$APP_DIR/.next/" "$DEPLOY_HOST:$REMOTE_APP/.next/"

if [[ "$DRY_RUN" == true ]]; then
    echo "Dry run complete; production was not restarted or verified."
    exit 0
fi

echo "Restarting $PROCESS_NAME..."
ssh "${SSH_ARGS[@]}" "$DEPLOY_HOST" \
    "cd '$REMOTE_APP' && pm2 restart '$PROCESS_NAME' && pm2 status '$PROCESS_NAME'"

echo "Verifying production..."
RWCWX_PUBLIC_URL="$PUBLIC_URL" "$SCRIPT_DIR/verify.sh"

build_id="$(<"$APP_DIR/.next/BUILD_ID")"
echo "Frontend deployment complete: $PUBLIC_URL/reports/month"
echo "Build ID: $build_id"
