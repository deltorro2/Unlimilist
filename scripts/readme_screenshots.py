"""Draws the README screenshots from a synthetic Board, so your own Tasks are never shown.

    uv run python scripts/readme_screenshots.py

Writes docs/board.png, docs/board-filtered.png and docs/task-dialog.png. The Board lives in memory only, and its clock is
pinned so every Urgency (Due soon, Overdue, Start passed) shows up the same way on every run.
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

    window = MainWindow(board)
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

    print(f"Wrote board.png, board-filtered.png and task-dialog.png in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
