#!/usr/bin/env bash

set -euo pipefail

PUBLIC_URL="${RWCWX_PUBLIC_URL:-https://rwcweather.com}"
VERIFY_DIR="$(mktemp -d "${TMPDIR:-/tmp}/rwcweather-verify.XXXXXX")"
trap 'rm -rf "$VERIFY_DIR"' EXIT

for command in curl python3; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Required command not found: $command" >&2
        exit 1
    fi
done

curl --fail --silent --show-error \
    --retry 5 --retry-delay 2 \
    "$PUBLIC_URL/reports/alltime" > "$VERIFY_DIR/alltime.html"

for marker in obs-monthly-matrix obs-alltime-summary; do
    if ! grep -q "$marker" "$VERIFY_DIR/alltime.html"; then
        echo "All-time page marker $marker was not found in the production page." >&2
        exit 1
    fi
done

old_url_target="$(curl --silent --output /dev/null --write-out '%{http_code} %{redirect_url}' \
    --retry 5 --retry-delay 2 "$PUBLIC_URL/reports/month")"
if [[ "$old_url_target" != "308 $PUBLIC_URL/reports/alltime" && "$old_url_target" != "301 $PUBLIC_URL/reports/alltime" ]]; then
    echo "Old /reports/month URL did not redirect to /reports/alltime: $old_url_target" >&2
    exit 1
fi

curl --fail --silent --show-error \
    --retry 5 --retry-delay 2 \
    "$PUBLIC_URL/api/var/all_periods/temp/avg/?start=20210101&include_today=1" \
    > "$VERIFY_DIR/api.json"

python3 - "$VERIFY_DIR/api.json" <<'PY'
import json
import sys

with open(sys.argv[1]) as response_file:
    response = json.load(response_file)

result = response.get("result", {})
for period in ("daily", "monthly", "yearly"):
    if not result.get(period):
        raise SystemExit(f"Production API returned no {period} results")

print(
    "Verified all-time page, redirect and API: "
    f"{len(result['daily'])} days, "
    f"{len(result['monthly'])} months, "
    f"{len(result['yearly'])} years"
)
PY
