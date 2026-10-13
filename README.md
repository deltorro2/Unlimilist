# Unlimilist

A personal desktop Kanban for Tasks. The vocabulary is in [CONTEXT.md](CONTEXT.md), and design decisions are in [docs/adr](docs/adr).

## Building

### Prerequisites

- [uv](https://docs.astral.sh/uv/). It installs the pinned Python (3.13, see `.python-version`) and every dependency, so you don't need a separate Python install.
  ```sh
  brew install uv        # or: curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- macOS to build the `.app` bundle. On Windows or Linux the same script builds a plain executable folder instead.

### Steps

```sh
git clone https://github.com/deltorro2/Unlimilist.git
cd Unlimilist
uv sync                        # create .venv with Python 3.13 and all dependencies
uv run pytest                  # run the tests (Board domain + pytest-qt UI)
uv run python -m unlimilist    # run from source
./scripts/build_app.sh         # build the app with PyInstaller
```

`build_app.sh` writes `dist/Unlimilist.app` on macOS, using the icon `assets/Unlimilist.icns` and stamping the bundle with the app version. It then ad-hoc signs the bundle, so it runs on the Mac that built it. On another Mac, Gatekeeper may ask you to confirm the first launch (right-click → Open). To install it, drag `dist/Unlimilist.app` into `/Applications`.

`build/`, `dist/` and the generated `*.spec` file are build output and are not committed.

## Data

Each Task is stored as one Markdown file in the app-data folder (`~/Library/Application Support/Unlimilist/tasks` on macOS). The files are read when the app starts.

## Version and icon

The version lives in `src/unlimilist/__init__.py` and is shown next to the app name. The app icon is `assets/Unlimilist.icns` for the bundle and `src/unlimilist/assets/app_icon.png` for the window.
