#!/usr/bin/env bash
# Builds dist/Unlimilist-<version>.dmg (macOS only): the app next to an Applications shortcut,
# so installing means dragging one onto the other. The layout is in scripts/dmg_settings.py.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "$(uname)" != "Darwin" ]]; then
  echo "build_dmg.sh only runs on macOS" >&2
  exit 1
fi

./scripts/build_app.sh
rm -rf build

version="$(uv run python -c 'import sys; sys.path.insert(0, "src"); import unlimilist; print(unlimilist.__version__)')"
dmg="dist/Unlimilist-$version.dmg"
rm -f "$dmg"
uv run dmgbuild \
  -s scripts/dmg_settings.py \
  -D app=dist/Unlimilist.app \
  -D icon=assets/Unlimilist.icns \
  "Unlimilist $version" \
  "$dmg"
echo "Built $dmg"
