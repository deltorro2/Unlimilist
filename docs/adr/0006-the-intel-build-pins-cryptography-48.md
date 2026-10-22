# The Intel build pins cryptography to 48.0.1

UnlimiList ships two macOS builds, Apple Silicon and Intel, both built on an Apple Silicon Mac. The Intel build uses an Intel Python run under Rosetta (`scripts/setup_intel_env.sh` makes `.venv-intel`). Its packages are the ones in `uv.lock`, with one exception: `cryptography` is pinned to **48.0.1**, the last release with an Intel macOS wheel. From 49, `cryptography` publishes Apple Silicon wheels only. The Apple Silicon build keeps the latest version.

The Secured Notes code uses only `AESGCM` and `Scrypt`, which are the same in both versions. A note encrypted by one build opens in the other: this was checked both ways when the Intel build was added.

## Considered Options

- **Pin 48.0.1 for both builds:** one lockfile, but Apple Silicon also stops getting `cryptography` security fixes.
- **Build the latest `cryptography` from source for Intel:** always current, but it needs an x86_64 Rust toolchain, and the build becomes slower and more fragile.
- **One universal (fat) app:** roughly doubles the download (Chromium twice), and every compiled package must be fused into universal form.

## Consequences

- The Intel build lags on `cryptography` security fixes. Revisit this when 48.x is too old: build from source, or drop Intel.
- Before an Intel release, run the test suite under the Intel Python: `arch -x86_64 .venv-intel/bin/python -m pytest`.
- Both builds need macOS 14 Sonoma (Qt 6.12). On Intel that means roughly 2018–2020 Macs.
