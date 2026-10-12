#!/usr/bin/env bash
# Dev Flask API on :5001 in the same process zone as prod (TZ=UTC).
# Needs MYSQL_URL (the dev DB). PORT and PYTHON can be overridden.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export TZ=UTC
exec "${PYTHON:-python3}" -c "from rwcwx.main import app; app.run(port=int('${PORT:-5001}'))"
