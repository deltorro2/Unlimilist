# Unlimilist

A personal desktop Kanban for Tasks. The vocabulary is in [CONTEXT.md](CONTEXT.md), and design decisions are in [docs/adr](docs/adr).

```sh
uv sync                        # install
uv run python -m unlimilist    # run from source
uv run pytest                  # tests (Board domain + pytest-qt UI)
./scripts/build_app.sh         # build dist/Unlimilist.app
```

Each Task is stored as one Markdown file in the app-data folder (`~/Library/Application Support/Unlimilist/tasks` on macOS). The files are read when the app starts.
