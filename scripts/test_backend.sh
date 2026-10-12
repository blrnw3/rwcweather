#!/usr/bin/env bash
# Run the backend tests twice: in UTC (prod's process zone) and in America/Los_Angeles,
# so time-zone bugs are caught in both directions. Extra args go to pytest.
#   PYTHON=venv/bin/python scripts/test_backend.sh -q
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PYTHON="${PYTHON:-python3}"
status=0
for zone in UTC America/Los_Angeles; do
    echo "=== backend tests with TZ=$zone ==="
    RWC_TEST_TZ="$zone" "$PYTHON" -m pytest "$@" tests || status=1
done
exit $status
