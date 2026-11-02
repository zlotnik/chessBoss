#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
CACHE_ROOT="$SCRIPT_DIR/.lambda-package-cache"
DEPENDENCY_DIR="$CACHE_ROOT/dependencies"
DEPENDENCY_KEY_FILE="$CACHE_ROOT/dependencies.key"
PACKAGE_DIR="$SCRIPT_DIR/lambda-package"
PACKAGE_ZIP="$SCRIPT_DIR/chessboss-lambda.zip"
TEMP_DEPENDENCIES=""

cleanup() {
    if [[ -n "$TEMP_DEPENDENCIES" && -d "$TEMP_DEPENDENCIES" ]]; then
        rm -rf "$TEMP_DEPENDENCIES"
    fi
}
trap cleanup EXIT

for command_name in "$PYTHON_BIN" zip sha256sum awk; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        printf 'Required command not found: %s\n' "$command_name" >&2
        exit 1
    fi
done

cd "$SCRIPT_DIR"
PYTHON_VERSION="$($PYTHON_BIN -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
PYTHON_PLATFORM="$($PYTHON_BIN -c 'import sysconfig; print(sysconfig.get_platform())')"
DEPENDENCY_KEY="$(cat requirements-lambda.txt; printf '\n%s\n%s\n' "$PYTHON_VERSION" "$PYTHON_PLATFORM" | sha256sum | awk '{ print $1 }')"

mkdir -p "$CACHE_ROOT"
REBUILD_DEPENDENCIES=1
if [[ "${FORCE_DEPENDENCY_REBUILD:-0}" != "1" && -d "$DEPENDENCY_DIR" && -f "$DEPENDENCY_KEY_FILE" ]]; then
    CACHED_KEY="$(<"$DEPENDENCY_KEY_FILE")"
    if [[ "$CACHED_KEY" == "$DEPENDENCY_KEY" ]]; then
        REBUILD_DEPENDENCIES=0
    fi
fi

if [[ "$REBUILD_DEPENDENCIES" == "1" ]]; then
    printf 'Dependency cache miss; installing Lambda dependencies...\n'
    TEMP_DEPENDENCIES="$CACHE_ROOT/dependencies.tmp.$$"
    rm -rf "$TEMP_DEPENDENCIES"
    mkdir -p "$TEMP_DEPENDENCIES"
    "$PYTHON_BIN" -m pip install --no-cache-dir -r requirements-lambda.txt -t "$TEMP_DEPENDENCIES"
    rm -rf "$DEPENDENCY_DIR"
    mv "$TEMP_DEPENDENCIES" "$DEPENDENCY_DIR"
    TEMP_DEPENDENCIES=""
    printf '%s\n' "$DEPENDENCY_KEY" > "$DEPENDENCY_KEY_FILE"
else
    printf 'Dependency cache hit; reusing installed Lambda dependencies.\n'
fi

rm -rf "$PACKAGE_DIR" "$PACKAGE_ZIP"
mkdir -p "$PACKAGE_DIR"
cp -a "$DEPENDENCY_DIR/." "$PACKAGE_DIR/"
cp api.py api_app.py cache.py lambda_api.py search_games.py "$PACKAGE_DIR/"
mkdir -p "$PACKAGE_DIR/data_providers"
cp data_providers/__init__.py data_providers/base.py data_providers/s3.py "$PACKAGE_DIR/data_providers/"

(
    cd "$PACKAGE_DIR"
    zip -qr "$PACKAGE_ZIP" . -x '*__pycache__*' '*.pyc'
)

printf 'Created %s\n' "$PACKAGE_ZIP"