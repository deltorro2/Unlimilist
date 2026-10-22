#!/usr/bin/env bash
# Builds dist/Unlimilist.app (macOS) or dist/Unlimilist (Windows/Linux): the normal build, reading your real
# Tasks in .../Unlimilist/tasks and Notes in .../Unlimilist/notes. On a Mac it is built for this Mac's chip.
#
#   ./scripts/build_app.sh --test
#
# builds dist/Unlimilist Test.app instead: it reads .../Unlimilist/test and .../Unlimilist/test-notes, shows TEST
# in its title, has its own bundle id so it can sit beside the real app, and the test Tasks and Notes in its
# folders are refreshed. It is for manual testing only and never gets a DMG.
#
#   ./scripts/build_app.sh --intel
#
# builds the app for Intel Macs, in dist/intel/, on an Apple Silicon Mac: with the Intel Python in .venv-intel
# (made by setup_intel_env.sh on first use), run under Rosetta. It can be combined with --test.
set -euo pipefail
cd "$(dirname "$0")/.."

test_build=false
intel=false
for option in "$@"; do
  case "$option" in
    --test) test_build=true ;;
    --intel) intel=true ;;
    *) echo "Unknown option: $option (use --test and/or --intel)" >&2; exit 1 ;;
  esac
done

name=Unlimilist
bundle_id=com.unlimilist.app
extra_data=()
if $test_build; then
  name="Unlimilist Test"
  bundle_id=com.unlimilist.app.test
  marker_dir=build/test-marker
  mkdir -p "$marker_dir"
  : > "$marker_dir/TEST_BUILD"  # the app looks for this file to know it is a test build
  extra_data=(--add-data "$marker_dir/TEST_BUILD:unlimilist")
fi

# Which Python builds it: this project's (uv), or the Intel one under Rosetta, into its own dist/ and build/ folders.
if $intel; then
  [[ -x .venv-intel/bin/python ]] || ./scripts/setup_intel_env.sh
  python=(/usr/bin/arch -x86_64 .venv-intel/bin/python)
  dist=dist/intel
  work=build/intel
  arch_options=(--target-arch x86_64)
else
  python=(uv run python)
  dist=dist
  work=build
  arch_options=()
fi

"${python[@]}" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "$name" \
  --osx-bundle-identifier "$bundle_id" \
  --icon assets/Unlimilist.icns \
  --distpath "$dist" \
  --workpath "$work" \
  --add-data src/unlimilist/assets:unlimilist/assets \
  ${extra_data[@]+"${extra_data[@]}"} \
  ${arch_options[@]+"${arch_options[@]}"} \
  --paths src \
  src/unlimilist/__main__.py

# Stamp the bundle with the app version, then re-sign it since Info.plist changed.
if [[ "$(uname)" == "Darwin" ]]; then
  version="$(uv run python -c 'import sys; sys.path.insert(0, "src"); import unlimilist; print(unlimilist.__version__)')"
  plist="$dist/$name.app/Contents/Info.plist"
  # macOS wants bundle versions as plain numbers, so a pre-release such as 1.6.0rc1 is stamped as 1.6.0.
  bundle_version="$(echo "$version" | sed -E 's/^([0-9]+(\.[0-9]+)*).*/\1/')"
  plutil -replace CFBundleShortVersionString -string "$bundle_version" "$plist"
  plutil -replace CFBundleVersion -string "$bundle_version" "$plist"
  plutil -replace LSMinimumSystemVersion -string "14.0" "$plist"  # Qt 6.12 needs macOS 14 Sonoma
  codesign --force --deep --sign - "$dist/$name.app"
fi

if $test_build; then
  uv run python scripts/make_test_tasks.py  # the test folder, never the real tasks folder
  uv run python scripts/make_test_notes.py  # the test-notes folder, never the real notes folder
fi
