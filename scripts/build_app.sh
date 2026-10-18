#!/usr/bin/env bash
# Builds dist/Unlimilist.app (macOS) or dist/Unlimilist (Windows/Linux): the normal build, reading your real
# Tasks in .../Unlimilist/tasks.
#
#   ./scripts/build_app.sh --test
#
# builds dist/Unlimilist Test.app instead: it reads .../Unlimilist/test, shows TEST in its title, has its own
# bundle id so it can sit beside the real app, and the test Tasks in its folder are refreshed. It is for manual
# testing only and never gets a DMG.
set -euo pipefail
cd "$(dirname "$0")/.."

name=Unlimilist
bundle_id=com.unlimilist.app
extra_data=()
if [[ "${1:-}" == "--test" ]]; then
  name="Unlimilist Test"
  bundle_id=com.unlimilist.app.test
  marker_dir=build/test-marker
  mkdir -p "$marker_dir"
  : > "$marker_dir/TEST_BUILD"  # the app looks for this file to know it is a test build
  extra_data=(--add-data "$marker_dir/TEST_BUILD:unlimilist")
fi

uv run pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "$name" \
  --osx-bundle-identifier "$bundle_id" \
  --icon assets/Unlimilist.icns \
  --add-data src/unlimilist/assets:unlimilist/assets \
  ${extra_data[@]+"${extra_data[@]}"} \
  --paths src \
  src/unlimilist/__main__.py

# Stamp the bundle with the app version, then re-sign it since Info.plist changed.
if [[ "$(uname)" == "Darwin" ]]; then
  version="$(uv run python -c 'import sys; sys.path.insert(0, "src"); import unlimilist; print(unlimilist.__version__)')"
  plist="dist/$name.app/Contents/Info.plist"
  # macOS wants bundle versions as plain numbers, so a pre-release such as 1.6.0rc1 is stamped as 1.6.0.
  bundle_version="$(echo "$version" | sed -E 's/^([0-9]+(\.[0-9]+)*).*/\1/')"
  plutil -replace CFBundleShortVersionString -string "$bundle_version" "$plist"
  plutil -replace CFBundleVersion -string "$bundle_version" "$plist"
  codesign --force --deep --sign - "dist/$name.app"
fi

if [[ "$name" == "Unlimilist Test" ]]; then
  uv run python scripts/make_test_tasks.py  # the test folder, never the real tasks folder
fi
