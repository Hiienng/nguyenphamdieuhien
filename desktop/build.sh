#!/usr/bin/env bash
# Build the Getify desktop app for the current OS (macOS -> .app, Windows -> .exe via build.ps1).
# Run from the desktop/ directory.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

echo "==> Installing desktop build deps"
"$PY" -m pip install --upgrade pip >/dev/null
"$PY" -m pip install -r requirements-desktop.txt

echo "==> Cleaning previous build"
rm -rf build dist

echo "==> Running PyInstaller"
"$PY" -m PyInstaller --noconfirm --clean Getify.spec

echo "==> Done. Output in: desktop/dist/"
ls -la dist
