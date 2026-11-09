#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-$SCRIPT_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON" ]]; then
  echo "Python environment not found at $PYTHON. Run 'make install' first." >&2
  exit 1
fi

cd "$SCRIPT_DIR"
exec "$PYTHON" -m search_benchmark.search_performance