# UnlimiList - personal multi-lane task manager for macOS (Windows support on demand)


## Releases
See [all available releases](https://github.com/deltorro2/Unlimilist/releases).

[![Latest Release](https://img.shields.io/github/v/release/deltorro2/Unlimilist)](https://github.com/deltorro2/Unlimilist/releases/latest)

## Description
I have to participate in a large number of different activities, each of which generates multiple tasks. Some of these tasks have strict deadlines, while others do not.
At any given time, I work on several tasks in parallel, each at a different stage of completion. Every task has its own priority, which is constantly changing.
In addition, as I work on these tasks, I accumulate various pieces of context-specific information associated with each one, such as phone numbers, code snippets, links, and so on. I would like to store this information alongside the relevant task.
One important requirement is that the system must work regardless of internet connectivity (local-first).
None of the tools I’ve evaluated (Jira, Todoist, TickTick, Google Tasks, etc.) fully meet my requirements. At the same time, they come with an incredible number of features that are completely unnecessary for me. 
What I need is a very simple, Kanban-based task management system (Trello too simple) which presents a huge number of ToDo's and Tasks in the usable form and allows simple triage them by importance level. And that’s when I decided that if I wanted it done right, I’d have to build it myself…



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

`build_app.sh` writes `dist/Unlimilist.app` on macOS, using the icon `assets/Unlimilist.icns` and stamping the bundle with the app version. It then ad-hoc signs the bundle, so it runs on the Mac that built it.

### macOS installer (DMG)

```sh
./scripts/build_dmg.sh         # builds the app, then dist/Unlimilist-<version>.dmg
```

The DMG opens a window with Unlimilist next to an Applications shortcut. To install, drag the app onto Applications. To uninstall, drag it from Applications to the Trash; your Tasks stay in the data folder. The window layout is in `scripts/dmg_settings.py` and is written by [dmgbuild](https://dmgbuild.readthedocs.io), so building needs no Finder permissions.

The app is built for Apple Silicon (arm64) only. It isn't signed with an Apple Developer ID or notarized, so on the first launch macOS says it can't verify the developer. Right-click the app in Applications and choose **Open**, then **Open** again; after that it opens normally.

`build/`, `dist/` and the generated `*.spec` file are build output and are not committed.

## Data

Each Task is stored as one Markdown file in the app-data folder (`~/Library/Application Support/Unlimilist/tasks` on macOS). The files are read when the app starts.

## Version and icon

The version lives in `src/unlimilist/__init__.py` and is shown next to the app name. The app icon is `assets/Unlimilist.icns` for the bundle and `src/unlimilist/assets/app_icon.png` for the window.
