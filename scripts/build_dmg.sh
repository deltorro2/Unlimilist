#!/usr/bin/env bash
# Builds the installer DMG (macOS only): the app next to an Applications shortcut, so installing means dragging one
# onto the other. The layout is in scripts/dmg_settings.py.
#
#   ./scripts/build_dmg.sh            # dist/Unlimilist-<version>-AppleSilicon.dmg
#   ./scripts/build_dmg.sh --intel    # dist/Unlimilist-<version>-Intel.dmg, built under Rosetta (see build_app.sh)
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "$(uname)" != "Darwin" ]]; then
  echo "build_dmg.sh only runs on macOS" >&2
  exit 1
fi

if [[ "${1:-}" == "--intel" ]]; then
  ./scripts/build_app.sh --intel
  app=dist/intel/Unlimilist.app
  chip=Intel
else
  ./scripts/build_app.sh
  app=dist/Unlimilist.app
  chip=AppleSilicon
fi
rm -rf build

version="$(uv run python -c 'import sys; sys.path.insert(0, "src"); import unlimilist; print(unlimilist.__version__)')"
dmg="dist/Unlimilist-$version-$chip.dmg"
rm -f "$dmg"
uv run dmgbuild \
  -s scripts/dmg_settings.py \
  -D app="$app" \
  -D icon=assets/Unlimilist.icns \
  "Unlimilist $version" \
  "$dmg"
echo "Built $dmg"
