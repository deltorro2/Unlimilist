#!/usr/bin/env bash
# Makes .venv-intel: an Intel (x86_64) Python 3.13 with the app's dependencies, for building and testing the Intel
# app on an Apple Silicon Mac (it runs under Rosetta). The packages are those in uv.lock, except cryptography: its
# last Intel Mac wheel is 48.0.1 (see docs/adr/0006-the-intel-build-pins-cryptography-48.md).
#
#   ./scripts/setup_intel_env.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if ! /usr/bin/arch -x86_64 /usr/bin/true 2>/dev/null; then
  echo "Rosetta 2 is needed to build the Intel app: softwareupdate --install-rosetta" >&2
  exit 1
fi

python="cpython-3.13-macos-x86_64-none"
uv python install "$python"
rm -rf .venv-intel
uv venv --quiet --python "$python" .venv-intel

mkdir -p build
uv export --frozen --no-hashes --no-emit-project --format requirements-txt \
  | sed -E 's/^cryptography==[^ ;]*/cryptography==48.0.1/' > build/intel-requirements.txt
uv pip install --quiet --python .venv-intel/bin/python -r build/intel-requirements.txt
uv pip install --quiet --python .venv-intel/bin/python --no-deps -e .  # the app itself, for the tests
echo "Made .venv-intel: $(/usr/bin/arch -x86_64 .venv-intel/bin/python -c 'import platform, sys; print(platform.machine(), sys.version.split()[0])')"
