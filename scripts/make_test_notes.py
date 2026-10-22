"""Fills the test-notes folder with made-up Notes for testing by hand: the folder the test build reads.

    uv run python scripts/make_test_notes.py            # add (or refresh) the test Notes
    uv run python scripts/make_test_notes.py --remove   # delete them again
    uv run python scripts/make_test_notes.py --folder /some/dir

The default folder is ~/Library/Application Support/Unlimilist/test-notes (the test build's), never your real
notes folder. Every test Note is a file named manual-test-NN.md, so other Notes you made while testing stay. They
are all Open (one is a long Note full of Mermaid diagrams): a Secured Note needs your Notebook password, so make
those in the app. Quit the app before running this: the app reads the folder when it starts.
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


DIAGRAMS_BODY = """# Every kind of diagram

A long Note with many Mermaid diagrams between ordinary Markdown, to check View mode: each diagram draws, wide ones
scale down to fit, the text between them keeps its spacing, and Find in Note still finds words around them.
The last diagram is broken on purpose: it shows its code under a red error.

## 1. Flowchart: how a release goes

Features land on **dev**; a pull request brings them to *main*, where releases are tagged.

```mermaid
flowchart LR
  idea([Idea]) --> grill{Grilled?}
  grill -- no --> idea
  grill -- yes --> dev[Build on dev]
  dev --> tests{Tests green?}
  tests -- no --> dev
  tests -- yes --> pr[Pull request]
  pr --> main[(main)]
  main --> tag[Tag vX.Y.Z]
  tag --> dmg[/DMG on GitHub/]
```

- [x] Grill the idea
- [x] Build it test-first
- [ ] Publish the release

## 2. Sequence: Esc on a shown Note

```mermaid
sequenceDiagram
  actor You
  participant Shown as Show Note
  participant List as Notebook list
  You->>Shown: press Esc
  Shown->>Shown: save the edits
  Shown-->>List: back, same search and sort
  List-->>You: the Note left is selected
  Note over You,List: With the Find bar open, Esc closes only the bar
```

> Tip: the same works with the ← Notebook button.

## 3. Class diagram: the Notebook's parts

```mermaid
classDiagram
  class Notebook {
    +notes() list
    +create(title, body) Note
    +save(id, title, body) Note
    +delete(id)
  }
  class Note {
    +id
    +title
    +body
    +tags
    +secured bool
  }
  class NoteSearch {
    +search(text) SearchResult
    +flush()
  }
  Notebook "1" --> "*" Note : owns
  NoteSearch --> Notebook : indexes
```

## 4. State diagram: a Task's Stages

```mermaid
stateDiagram-v2
  [*] --> Inbox
  Inbox --> InProcess : start
  InProcess --> Inbox : put back
  InProcess --> Done : finish
  Inbox --> Done : finish
  Done --> InProcess : reopen
  Done --> [*]
```

| Stage | Can be deleted | Lanes |
| --- | --- | --- |
| Inbox | yes | Someday, Time-limited |
| In Process | no | Someday, Time-limited |
| Done | yes | one list |

## 5. Gantt: a week of work

```mermaid
gantt
  title Release week
  dateFormat YYYY-MM-DD
  section Build
  Notebook search     :done,    s1, 2026-10-19, 2d
  Raised rows         :done,    s2, after s1, 1d
  Mermaid in View     :active,  s3, after s2, 2d
  section Ship
  Test build          :         s4, after s3, 1d
  Release 2.1         :milestone, s5, after s4, 0d
```

## 6. Pie: where the time went

```mermaid
pie showData
  title Time this week
  "Building" : 45
  "Testing" : 30
  "Grilling" : 15
  "Releasing" : 10
```

## 7. Entity relationship: the files

```mermaid
erDiagram
  TASK ||--o{ TAG : has
  NOTE ||--o{ TAG : has
  NOTE ||--o| SECURED_BODY : "may have"
  TASK {
    string id
    string title
    string stage
  }
  NOTE {
    string id
    string title
    string type
  }
```

## 8. Mind map: ideas for next time

```mermaid
mindmap
  root((UnlimiList))
    Board
      Folded Done
      Card font size
    Notebook
      Search
      Secured Notes
      Mermaid
    Someday
      Sync between Macs
      Reminders
```

## 9. A wide flowchart that has to shrink to fit

```mermaid
flowchart LR
  a1[Step one] --> a2[Step two] --> a3[Step three] --> a4[Step four] --> a5[Step five]
  a5 --> a6[Step six] --> a7[Step seven] --> a8[Step eight] --> a9[Step nine] --> a10[Step ten]
```

## 10. A broken diagram (on purpose)

```mermaid
flowchart LR
  this line --> is not ( valid mermaid
```

## The end

Some closing text after all the diagrams, with a [link to Mermaid's docs](https://mermaid.js.org) and `code`.
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
        dict(title="Every kind of diagram", body=DIAGRAMS_BODY, tags=("diagrams", "work"), created=3, opened=None),
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
