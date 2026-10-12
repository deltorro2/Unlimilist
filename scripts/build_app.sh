#!/usr/bin/env bash
# Builds dist/Unlimilist.app (macOS) or dist/Unlimilist (Windows/Linux).
set -euo pipefail
cd "$(dirname "$0")/.."
uv run pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name Unlimilist \
  --osx-bundle-identifier com.unlimilist.app \
  --paths src \
  src/unlimilist/__main__.py
