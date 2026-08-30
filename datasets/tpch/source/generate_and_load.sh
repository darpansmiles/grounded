#!/usr/bin/env bash
# Generate the decided TPC-H SF=0.5 source and load it into local PostgreSQL.
set -euo pipefail

readonly PROJECT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec "$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/datasets/tpch/source/generate_and_load.py" "$@"
