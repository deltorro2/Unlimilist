"""Draws the README screenshots from a synthetic Board and Notebook, so your own Tasks and Notes are never shown.

    uv run python scripts/readme_screenshots.py

It draws off the screen at 2x (Retina) size, whatever screen you have, with the web view (View mode) in software, so
its diagrams are captured too.

Writes docs/board.png, docs/board-filtered.png, docs/task-dialog.png, docs/notebook.png, docs/notebook-search.png,
docs/note.png (View mode, with Mermaid diagrams) and docs/note-edit.png (Edit mode). The Board and Notebook live in memory only, and their clocks are pinned so every Urgency (Due soon,
Overdue, Start passed) and every date shows up the same way on every run.
"""

import os
import sys
import time

# Before Qt starts: off the screen, at 2x, and the web view drawn in software so grab() can capture it.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "2")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QApplication, QWidget

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from unlimilist import app as unlimilist_app  # noqa: E402
from unlimilist.board import Board  # noqa: E402
from unlimilist.domain import Activity, Stage  # noqa: E402
from unlimilist.notebook import Notebook, NoteType  # noqa: E402
from unlimilist.ui.main_window import MainWindow  # noqa: E402
from unlimilist.ui.task_dialog import TaskDialog  # noqa: E402

TODAY = date(2026, 10, 13)
SCALE = 2  # drawn at Retina resolution, so the images stay sharp on GitHub
ASK, CALL, MEETING = Activity.ASK, Activity.PHONE_CALL, Activity.MEETING
CODE, MILESTONE = Activity.DEVELOP_CODE, Activity.MILESTONE


def days(n: int) -> date:
    return TODAY + timedelta(days=n)


def synthetic_board() -> tuple[Board, str]:
    now = [datetime.combine(TODAY, datetime.min.time()).replace(hour=9)]

    def clock() -> datetime:
        now[0] += timedelta(minutes=1)
        return now[0]

    board = Board(clock=clock)
    add = board.add_task

    # Inbox, Someday: ranked by Priority.
    add("Plan the vegetable garden", details="Raised beds along the fence #home #garden")
    showcase = add(
        "Refactor the sync module",
        activity=CODE,
        details="- [x] Split the reader from the writer\n- [ ] Retry on network errors\n- [ ] Add tests\n\n"
        "Keep the public API as it is. #work",
        usable_data="Branch: `refactor/sync`\n\nhttps://github.com/deltorro2/Unlimilist",
    )
    add("Call grandma", activity=CALL, details="Ask about the family recipes #family")
    add("Ask Sam when book club meets", activity=ASK, details="Bring the second volume #reading")
    add("Read Designing Data-Intensive Applications", details="Chapters 5 to 7 #reading #work")

    # Inbox, Time-limited: one Task for each Urgency.
    add("Call the insurer", activity=CALL, deadline=days(-3), details="Send the receipts #finance #car")
    add("Book flights to Lisbon", due_date=days(-2), deadline=days(40), details="Window seats #travel")
    add("Pay the electricity bill", activity=MILESTONE, deadline=TODAY, details="#finance #home")
    add("Quarterly planning", activity=MEETING, due_date=days(5), deadline=days(12), details="Agenda and the numbers for #client-x #work")
    add(
        "Launch the public beta",
        activity=MILESTONE,
        deadline=days(30),
        details="- [ ] Landing page\n- [ ] Invite list\n- [ ] Feedback form\n\n#work #release",
    )

    # In Process.
    for title, fields in [
        ("Write the onboarding guide", {"details": "- [x] Install steps\n- [ ] First Task walkthrough\n\n#work #docs"}),
        ("Fix the flaky login test", {"activity": CODE, "details": "Fails about once in twenty runs #work"}),
        ("Client demo", {"activity": MEETING, "deadline": days(1), "details": "Show the new Board #client-x"}),
        ("Call the plumber back", {"activity": CALL, "deadline": days(-1), "details": "#home"}),
        ("Release 1.5", {"activity": CODE, "due_date": days(-3), "deadline": days(4), "usable_data": "Release checklist", "details": "#release #work #client-x"}),
    ]:
        board.move_task(add(title, **fields).id, Stage.IN_PROCESS)

    # Done: completed Tasks, most recent first.
    for title, fields in [
        ("Call the bank", {"activity": CALL, "details": "#finance"}),
        ("Fix the bike", {"details": "New chain"}),
        ("Team retrospective", {"activity": MEETING, "details": "#work"}),
        ("Renew passport", {"activity": MILESTONE, "details": "- [x] Photos\n- [x] Form\n\n#travel"}),
    ]:
        board.move_task(add(title, **fields).id, Stage.DONE)

    return board, showcase.id


ARCHITECTURE = """# Payments service: architecture

The payments service takes **card and bank payments** for the web shop. It runs as three containers
behind the API gateway; this Note is the reference for the *Q4 hardening* work.

## Request flow

```mermaid
flowchart LR
  client([Web shop]) --> gateway[API gateway]
  gateway --> api[Payments API]
  api --> queue[(Event queue)]
  queue --> worker[Settlement worker]
  worker --> bank[[Bank adapter]]
  api --> db[(Postgres)]
```

## Checkout sequence

```mermaid
sequenceDiagram
  participant Shop
  participant API as Payments API
  participant Bank
  Shop->>API: POST /payments
  API->>Bank: authorise
  Bank-->>API: approved
  API-->>Shop: 201 Created
```

## Service levels

| Endpoint | p95 latency | Error budget |
| --- | --- | --- |
| `POST /payments` | 180 ms | 0.1 % |
| `GET /payments/{id}` | 40 ms | 0.5 % |

## Open items

- [x] Retry with back-off on bank timeouts
- [x] Idempotency keys on `POST /payments`
- [ ] Alert on settlement lag over 5 minutes

> Owner: platform team. Review the error budget every sprint.
"""

ROADMAP = """# Q4 roadmap

Three themes for the quarter: **reliability**, **onboarding** and the *public beta*.

```mermaid
gantt
  dateFormat YYYY-MM-DD
  section Reliability
  Payments hardening   :done,   r1, 2026-10-01, 14d
  Settlement alerts    :active, r2, after r1, 10d
  section Beta
  Invite list          :        b1, 2026-10-20, 7d
  Public beta          :milestone, b2, 2026-11-12, 0d
```

- Payments hardening: see *Payments service: architecture*
- Onboarding guide: draft in review
"""


def synthetic_notebook() -> tuple[Notebook, str, str]:
    now = [datetime.combine(TODAY - timedelta(days=12), datetime.min.time()).replace(hour=8)]

    def clock() -> datetime:
        now[0] += timedelta(hours=5, minutes=17)
        return now[0]

    notebook = Notebook(clock=clock)
    add = notebook.create
    add("Reading list", "- Designing Data-Intensive Applications\n- Release It!", tags=("reading",))
    add("Client X kickoff notes", "Goals, budget, the payments release date and the team.", tags=("client-x", "work"))
    add("Production access keys", "Gateway: …\nDatabase: …", tags=("work",), note_type=NoteType.SECURED, password="demo")
    add("Incident review: settlement lag", "Root cause: the payments worker stalled on a bank timeout.", tags=("work",))
    add("", "Shipped the retry fix. Calm on-call week.", tags=("journal",))  # a Daily note
    add("Hiring loop: backend engineer", "Four interviews, one take-home.", tags=("hiring", "work"))
    roadmap = add("Q4 roadmap", ROADMAP, tags=("planning", "work"))
    add("Payments release checklist", "- [ ] Load test\n- [ ] Runbook\n- [ ] Release notes", tags=("release", "work"))
    architecture = add("Payments service: architecture", ARCHITECTURE, tags=("architecture", "work"))
    for title in ("Reading list", "Q4 roadmap"):
        notebook.mark_opened(next(n.id for n in notebook.notes() if n.title == title))
    return notebook, architecture.id, roadmap.id


def settle(app: QApplication) -> None:
    for _ in range(30):
        app.processEvents()


def save(widget: QWidget, path: Path) -> None:
    """The widget as on screen, at the screen's resolution (Retina here). grab() also catches the web view's
    content, which render() leaves blank."""
    widget.grab().save(str(path))


def wait_rendered(app: QApplication, viewer) -> None:
    """Until View mode's web page, diagrams included, is drawn."""
    for _ in range(300):
        if viewer.is_rendered():
            break
        app.processEvents()
        time.sleep(0.02)
    for _ in range(20):  # a moment more for the last paint
        app.processEvents()
        time.sleep(0.02)


def main() -> int:
    # View mode's web engine has to be loaded before the QApplication exists, as in the app.
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    import PySide6.QtWebEngineWidgets  # noqa: F401

    app = QApplication(sys.argv)
    app.setApplicationName("Unlimilist")
    app.setStyle("Fusion")
    app.setPalette(unlimilist_app._light_palette())
    app.setStyleSheet(unlimilist_app.STYLESHEET)

    board, showcase_id = synthetic_board()
    out = ROOT / "docs"

    notebook, architecture_id, roadmap_id = synthetic_notebook()
    window = MainWindow(board, notebook=notebook)
    window.resize(1500, 950)
    window.show()
    settle(app)
    save(window, out / "board.png")

    for tag in ("client-x", "work"):
        window.toggle_tag(tag)
    settle(app)
    save(window, out / "board-filtered.png")
    window.clear_tag_filter()

    dialog = TaskDialog(board, board.task(showcase_id), parent=window)
    dialog.show()
    dialog.title_edit.deselect()
    dialog.title_edit.clearFocus()
    settle(app)
    save(dialog, out / "task-dialog.png")
    dialog.close()

    window.show_notebook()
    settle(app)
    save(window, out / "notebook.png")

    notes = window.notebook_view
    notes.search_field.setText("payments release")
    notes.apply_search("payments release")
    settle(app)
    notes.toast().dismiss()
    save(window, out / "notebook-search.png")
    notes.clear_search()

    notes.open_note(architecture_id)
    wait_rendered(app, notes.note_page.viewer)
    save(window, out / "note.png")

    notes.note_page.edit_button.click()
    settle(app)
    save(window, out / "note-edit.png")
    notes.show_table()

    print(f"Wrote the Board, Task dialog and Notebook screenshots in {out}")
    del window  # its web view goes before the web engine
    return 0


if __name__ == "__main__":
    sys.exit(main())
