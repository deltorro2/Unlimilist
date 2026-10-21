"""Fills the test-notes folder with made-up Notes for testing by hand: the folder the test build reads.

    uv run python scripts/make_test_notes.py            # add (or refresh) the test Notes
    uv run python scripts/make_test_notes.py --remove   # delete them again
    uv run python scripts/make_test_notes.py --folder /some/dir

The default folder is ~/Library/Application Support/Unlimilist/test-notes (the test build's), never your real
notes folder. Every test Note is a file named manual-test-NN.md, so other Notes you made while testing stay. They
are all Open: a Secured Note needs your Notebook password, so make those in the app. Quit the app before running
this: the app reads the folder when it starts.
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QStandardPaths

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from unlimilist.note_store import MarkdownNoteStore  # noqa: E402
from unlimilist.notebook import Note, NoteType  # noqa: E402

PREFIX = "manual-test-"

RICH_BODY = """# Lisbon, three days

Plan for **day one** and *day two*, with ~~day three~~ cancelled.

## Places

- Alfama and tram 28
- Belém, for the `pastéis`
  - and the tower
1. Book the hotel
2. Buy tickets

- [x] Passport
- [ ] Adapter

> Go early: the queues get long.

| City | Days |
| --- | --- |
| Lisbon | 3 |
| Porto | 2 |

```
flight TP 1234, 07:40
```

[The tourist office](https://www.visitlisboa.com)
"""


def default_folder() -> Path:
    QCoreApplication.setApplicationName("Unlimilist")  # the same folder the app uses
    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)) / "test-notes"


def test_notes() -> list[dict]:
    """(Title, Body, Tags, minutes since creation, minutes since last opened or None)."""
    long_body = "\n\n".join(f"## Part {n}\n\n" + "A long paragraph to scroll through. " * 30 for n in range(1, 21))
    return [
        dict(title="Every kind of Markdown", body=RICH_BODY, tags=("travel", "family"), created=60, opened=5),
        dict(title="Never opened", body="Last opened shows a dash.", tags=("inbox",), created=30, opened=None),
        dict(title="Opened long ago", body="Created and opened weeks ago.", tags=(), created=40000, opened=30000),
        dict(title="A long Note", body=long_body, tags=("reading",), created=2000, opened=None),
        dict(
            title="Remember to ask the landlord about the heating, the leaking tap in the kitchen and the…",
            body="Remember to ask the landlord about the heating, the leaking tap in the kitchen and the parking "
            "permit before the winter starts.",
            tags=(),
            created=10,
            opened=None,
        ),
        dict(title="Daily note 1 Oct 2026", body="Slept well, ran 5 km.", tags=("daily", "health"), created=29000,
             opened=None),
        dict(title="Shares a Tag with Tasks", body="#work here is just text, not a Tag.", tags=("work",), created=90,
             opened=None),
        dict(title="שלום — non-Latin title", body="Hebrew in the title, ASCII in the file name.", tags=("Travel",),
             created=120, opened=None),
        dict(title="Empty body", body="", tags=(), created=200, opened=None),
        dict(title="Many Tags", body="Tags overflow the Tag area.", created=300, opened=None,
             tags=tuple("alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu".split())),
        dict(title="Big imported table", created=400, opened=None, tags=("finance",),
             body="| Month | Rent | Food |\n| --- | --- | --- |\n"
             + "\n".join(f"| {month} | 900 | {300 + n * 7} |" for n, month in enumerate(
                 "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()))),
    ]


def remove(folder: Path) -> int:
    paths = list(folder.glob(f"{PREFIX}*.md"))
    for path in paths:
        path.unlink()
    return len(paths)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder", type=Path, help="the notes folder (default: the test build's folder)")
    parser.add_argument("--remove", action="store_true", help="delete the test Notes instead of adding them")
    options = parser.parse_args()
    folder = options.folder or default_folder()

    removed = remove(folder) if folder.exists() else 0
    if options.remove:
        print(f"Removed {removed} test Notes from {folder}")
        return 0

    store = MarkdownNoteStore(folder)
    now = datetime.now().replace(microsecond=0)
    notes = test_notes()
    for number, fields in enumerate(notes, start=1):
        opened = fields.pop("opened")
        store.save(
            Note(
                id=f"{PREFIX}{number:02d}",
                note_type=NoteType.OPEN,
                created_at=now - timedelta(minutes=fields.pop("created")),
                opened_at=now - timedelta(minutes=opened) if opened is not None else None,
                **fields,
            )
        )
    print(f"Wrote {len(notes)} test Notes to {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
