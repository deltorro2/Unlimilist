"""Draws the README screenshots from a synthetic Board and Notebook, so your own Tasks and Notes are never shown.

    uv run python scripts/readme_screenshots.py

Writes docs/board.png, docs/board-filtered.png, docs/task-dialog.png, docs/notebook.png, docs/notebook-search.png and
docs/note.png. The Board and Notebook live in memory only, and their clocks are pinned so every Urgency (Due soon,
Overdue, Start passed) and every date shows up the same way on every run.
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtGui import QPixmap
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


LISBON = """# Lisbon, five days

The plan for **May**: slow mornings, one big sight a day, and *no* taxis.

## Places

- Alfama and tram 28, early, before the crowds
- Belém, for the tower and the `pastéis`
- Sintra on a weekday

## Before we go

- [x] Passports
- [x] Book the flat near Graça
- [ ] Travel insurance

| Day | Plan |
| --- | --- |
| Mon | Alfama, fado in the evening |
| Tue | Belém and the river |
| Wed | Sintra |

> Ask Ana about the restaurant with the blue tiles.

[Visit Lisboa](https://www.visitlisboa.com)
"""


def synthetic_notebook() -> tuple[Notebook, str]:
    now = [datetime.combine(TODAY - timedelta(days=12), datetime.min.time()).replace(hour=8)]

    def clock() -> datetime:
        now[0] += timedelta(hours=5, minutes=17)
        return now[0]

    notebook = Notebook(clock=clock)
    add = notebook.create
    add("Reading list", "- Designing Data-Intensive Applications\n- The Overstory", tags=("reading",))
    add("Lisbon hotel shortlist", "Graça, Alfama or Príncipe Real.", tags=("travel",))
    add("Client X kickoff notes", "Goals, budget, the hotel booking for the team.", tags=("client-x", "work"))
    add("Wi-Fi and alarm codes", "Router: …\nAlarm: …", tags=("home",), note_type=NoteType.SECURED, password="demo")
    add("Garden plan", "Tomatoes along the fence, herbs by the door.", tags=("garden", "home"))
    add("", "Ran 5 km along the river. Slept well.", tags=("health",))  # a Daily note
    add("Release 2.0 checklist", "- [ ] Screenshots\n- [ ] DMG\n- [ ] Notes", tags=("release", "work"))
    lisbon = add("Trip to Lisbon", LISBON, tags=("travel", "family"))
    for title in ("Reading list", "Garden plan"):
        notebook.mark_opened(next(n.id for n in notebook.notes() if n.title == title))
    return notebook, lisbon.id


def settle(app: QApplication) -> None:
    for _ in range(30):
        app.processEvents()


def save(widget: QWidget, path: Path) -> None:
    image = QPixmap(widget.size() * SCALE)
    image.setDevicePixelRatio(SCALE)
    widget.render(image)
    image.save(str(path))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Unlimilist")
    app.setStyle("Fusion")
    app.setPalette(unlimilist_app._light_palette())
    app.setStyleSheet(unlimilist_app.STYLESHEET)

    board, showcase_id = synthetic_board()
    out = ROOT / "docs"

    notebook, lisbon_id = synthetic_notebook()
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
    notes.search_field.setText("lisbon hotel")
    notes.apply_search("lisbon hotel")
    settle(app)
    save(window, out / "notebook-search.png")
    notes.clear_search()

    notes.open_note(lisbon_id)
    settle(app)
    save(window, out / "note.png")

    print(f"Wrote the Board, Task dialog and Notebook screenshots in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
