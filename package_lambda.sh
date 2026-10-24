#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    printf 'Python executable not found: %s\n' "$PYTHON_BIN" >&2
    exit 1
fi

if ! command -v zip >/dev/null 2>&1; then
    printf 'zip is required. Install it with: sudo apt install zip\n' >&2
    exit 1
fi

cd "$SCRIPT_DIR"
rm -rf lambda-package chessboss-lambda.zip
mkdir -p lambda-package

"$PYTHON_BIN" -m pip install --no-cache-dir -r requirements-lambda.txt -t lambda-package/
cp api.py api_app.py cache.py lambda_api.py search_games.py lambda-package/
mkdir -p lambda-package/data_providers
cp data_providers/__init__.py data_providers/base.py data_providers/s3.py lambda-package/data_providers/

(
    cd lambda-package
    zip -qr ../chessboss-lambda.zip . -x '*__pycache__*' '*.pyc'
)

printf 'Created %s/chessboss-lambda.zip\n' "$SCRIPT_DIR"