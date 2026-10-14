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
  --icon assets/Unlimilist.icns \
  --add-data src/unlimilist/assets:unlimilist/assets \
  --paths src \
  src/unlimilist/__main__.py

# Stamp the bundle with the app version, then re-sign it since Info.plist changed.
if [[ "$(uname)" == "Darwin" ]]; then
  version="$(uv run python -c 'import sys; sys.path.insert(0, "src"); import unlimilist; print(unlimilist.__version__)')"
  plist=dist/Unlimilist.app/Contents/Info.plist
  # macOS wants bundle versions as plain numbers, so a pre-release such as 1.6.0rc1 is stamped as 1.6.0.
  bundle_version="$(echo "$version" | sed -E 's/^([0-9]+(\.[0-9]+)*).*/\1/')"
  plutil -replace CFBundleShortVersionString -string "$bundle_version" "$plist"
  plutil -replace CFBundleVersion -string "$bundle_version" "$plist"
  codesign --force --deep --sign - dist/Unlimilist.app
fi
