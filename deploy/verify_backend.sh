#!/usr/bin/env bash

set -euo pipefail

PUBLIC_URL="${RWCWX_PUBLIC_URL:-https://rwcweather.com}"
MAX_LIVE_SECONDS="${RWCWX_MAX_LIVE_SECONDS:-2.0}"
VERIFY_DIR="$(mktemp -d "${TMPDIR:-/tmp}/rwcweather-backend-verify.XXXXXX")"
trap 'rm -rf "$VERIFY_DIR"' EXIT

for command in curl python3; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Required command not found: $command" >&2
        exit 1
    fi
done

curl --fail --silent --show-error \
    --retry 5 --retry-delay 2 \
    "$PUBLIC_URL/api/lol" > "$VERIFY_DIR/lol.json"

live_seconds="$(curl --fail --silent --show-error \
    --retry 5 --retry-delay 2 \
    --output "$VERIFY_DIR/live.json" \
    --write-out '%{time_total}' \
    "$PUBLIC_URL/api/web/dashboard/live")"

python3 - \
    "$VERIFY_DIR/lol.json" \
    "$VERIFY_DIR/live.json" \
    "$live_seconds" \
    "$MAX_LIVE_SECONDS" <<'PY'
import json
import sys

lol_path, live_path, elapsed_raw, maximum_raw = sys.argv[1:]

with open(lol_path) as response_file:
    lol = json.load(response_file)
if lol.get("lol") != 42:
    raise SystemExit("Unexpected response from /api/lol")

with open(live_path) as response_file:
    live = json.load(response_file)

result = live.get("result", {})
required = {"now", "trends", "today", "last_rain", "rain_trend"}
missing = sorted(required.difference(result))
if missing:
    raise SystemExit(f"Live dashboard response is missing: {', '.join(missing)}")

elapsed = float(elapsed_raw)
maximum = float(maximum_raw)
if elapsed > maximum:
    raise SystemExit(
        f"Live dashboard took {elapsed:.3f}s; maximum allowed is {maximum:.3f}s"
    )

print(f"Verified backend API; live dashboard responded in {elapsed:.3f}s")
PY
