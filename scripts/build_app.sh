#!/usr/bin/env bash
# scripts/build_app.sh — Full pipeline: PyInstaller → electron-builder → .dmg
#
# Usage: bash scripts/build_app.sh
#
# Prerequisites:
#   - Python 3.13 at /opt/homebrew/bin/python3.13 (or on PATH as python3.13)
#   - Node.js + npm on PATH
#   - electron/ dependencies installed (npm install inside electron/)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Step 1: Build miktos-server (PyInstaller) ==="
/opt/homebrew/bin/python3.13 scripts/build_server.py

echo ""
echo "=== Step 2: Install electron npm dependencies ==="
cd electron
npm install

echo ""
echo "=== Step 3: Build .dmg with electron-builder ==="
npm run dist

echo ""
echo "=== Build complete ==="
ls -lh dist/*.dmg 2>/dev/null || ls -lh electron/dist/*.dmg 2>/dev/null || true
echo "Installer: electron/dist/Miktos-*.dmg"
