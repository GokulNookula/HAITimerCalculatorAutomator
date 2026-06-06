#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 build.py
echo
echo "Build finished. Your executable is inside the dist folder."
