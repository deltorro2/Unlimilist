"""Fills the test folder with made-up Tasks for testing by hand: the folder the test build reads.

    uv run python scripts/make_test_tasks.py            # add (or refresh) the test Tasks
    uv run python scripts/make_test_tasks.py --remove   # delete them again
    uv run python scripts/make_test_tasks.py --folder /some/dir

The default folder is ~/Library/Application Support/Unlimilist/test (the test build's), never your real tasks
folder. Every test Task is a file named manual-test-NN.md, so other Tasks you made while testing stay. Dates are
relative to today, so Overdue, Start passed and Due soon always show. Quit the app before running this:
the app reads the folder when it starts.
"""

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QStandardPaths

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from unlimilist.domain import Activity, Stage, Task  # noqa: E402
from unlimilist.store import MarkdownTaskStore  # noqa: E402

PREFIX = "manual-test-"
GENERAL, ASK, CALL, MEETING, CODE, MILESTONE = (
    Activity.GENERAL_TASK,
    Activity.ASK,
    Activity.PHONE_CALL,
    Activity.MEETING,
    Activity.DEVELOP_CODE,
    Activity.MILESTONE,
)
INBOX, IN_PROCESS, DONE = Stage.INBOX, Stage.IN_PROCESS, Stage.DONE
LONG_TITLE = (
    "Prepare the quarterly report for the board meeting with every number, every chart, a summary of the risks "
    "for next year and a short list of the decisions we need from them"
)
# Enough Tags that the sidebar has to scroll.
MANY_TAGS = " ".join(
    f"#{name}"
    for name in (
        "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau "
        "upsilon phi chi psi omega"
    ).split()
)


def default_folder() -> Path:
    QCoreApplication.setApplicationName("Unlimilist")  # the same folder the app uses
    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)) / "test"


def test_tasks(today: date) -> list[dict]:
    """What each test Task checks is in its Details."""

    def day(n: int) -> date:
        return today + timedelta(days=n)

    return [
        # Inbox, Someday: more than five, so the Column interleaves them with Time-limited Tasks.
        dict(title="Plan the vegetable garden", activity=GENERAL, details="Raised beds along the fence #home #garden"),
        dict(
            title="Refactor the sync module",
            activity=CODE,
            details="- [x] Split the reader from the writer\n- [ ] Retry on network errors\n- [ ] Add tests\n\n"
            "Unfinished Subtasks: dragging this to Done is refused with a balloon. #work #code",
            usable_data="Branch: `refactor/sync`\n\nhttps://github.com/deltorro2/Unlimilist",
        ),
        dict(title="Call grandma", activity=CALL, details="Ask about the family recipes #family"),
        dict(title=LONG_TITLE, activity=MEETING, details="A long title wraps under the Tag chip. #work #client-x #reports"),
        dict(title="Ask Dana about the invoice", activity=ASK, details="An Ask Task: pink badge. No Tags, so no chip."),
        dict(
            title="Long Tag cut in the chip",
            activity=GENERAL,
            details="The chip shows at most 12 characters. #reading-list-for-autumn #books #home",
        ),
        dict(title="Mixed case Tags", activity=GENERAL, details="#Work and #WORK are the same Tag as #work."),
        dict(
            title="Hashes that are not Tags",
            activity=GENERAL,
            details="No chip expected: issue#12, https://site.com/page#section, `#define` and [#link](https://a.com)",
            usable_data="#bank in Usable data is not a Tag either",
        ),
        dict(title="Pay #rent (a # in the Title is not a Tag)", activity=MILESTONE, details="Only #finance counts."),
        dict(title="Many Tags", activity=GENERAL, details=f"Fills the sidebar so it scrolls: {MANY_TAGS}"),
        # Inbox, Time-limited: one of each Urgency.
        dict(title="Call the insurer", activity=CALL, deadline=day(-3), details="Overdue: red border. #finance #car"),
        dict(
            title="Book flights to Lisbon",
            activity=GENERAL,
            due_date=day(-2),
            deadline=day(40),
            details="Start passed: red border. #travel",
        ),
        dict(title="Pay the electricity bill", activity=MILESTONE, deadline=day(1), details="Due soon: amber stripe. #finance #home"),
        dict(
            title="Quarterly planning",
            activity=MEETING,
            due_date=day(5),
            deadline=day(12),
            details="Agenda and the numbers #client-x #work",
        ),
        dict(
            title="Launch the public beta",
            activity=MILESTONE,
            deadline=day(30),
            details="- [ ] Landing page\n- [ ] Invite list\n\n#work #release",
        ),
        dict(title=LONG_TITLE, activity=CODE, deadline=day(20), details="A long Time-limited title: 3 lines, then dates. #work"),
        # In Process: a Task here can't be deleted.
        dict(stage=IN_PROCESS, title="Write the onboarding guide", activity=GENERAL, details="- [x] Install steps\n- [ ] First Task\n\n#work #docs"),
        dict(stage=IN_PROCESS, title="Fix the flaky login test", activity=CODE, details="Fails about once in twenty runs #work #code"),
        dict(stage=IN_PROCESS, title="Client demo", activity=MEETING, deadline=day(0), details="Show the new Board #client-x"),
        dict(stage=IN_PROCESS, title="Call the plumber back", activity=CALL, deadline=day(-1), details="#home"),
        dict(
            stage=IN_PROCESS,
            title="Release 1.6",
            activity=CODE,
            due_date=day(-3),
            deadline=day(4),
            details="- [x] Build\n- [x] Test\n\nAll Subtasks finished: this one can go to Done. #release #work #client-x",
        ),
        # Done.
        dict(stage=DONE, title="Call the bank", activity=CALL, details="#finance", completed=1),
        dict(stage=DONE, title="Team retrospective", activity=MEETING, details="#work", completed=2),
        dict(stage=DONE, title="Renew passport", activity=MILESTONE, details="- [x] Photos\n- [x] Form\n\n#travel", completed=3),
        dict(stage=DONE, title="Fix the bike", activity=GENERAL, details="New chain", completed=4),
    ]


def remove(folder: Path) -> int:
    files = sorted(folder.glob(f"{PREFIX}*.md"))
    for path in files:
        path.unlink()
    return len(files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder", type=Path, help="the tasks folder (default: the test build's folder)")
    parser.add_argument("--remove", action="store_true", help="delete the test Tasks instead of adding them")
    options = parser.parse_args()
    folder = options.folder or default_folder()

    removed = remove(folder) if folder.exists() else 0
    if options.remove:
        print(f"Removed {removed} test Tasks from {folder}")
        return 0

    store = MarkdownTaskStore(folder)
    today = date.today()
    start = datetime.now().replace(microsecond=0) - timedelta(days=7)
    for number, fields in enumerate(test_tasks(today), start=1):
        stage = fields.pop("stage", INBOX)
        completed = fields.pop("completed", None)
        task = Task(
            id=f"{PREFIX}{number:02d}",
            stage=stage,
            created_at=start + timedelta(minutes=number),
            completed_at=datetime.now().replace(microsecond=0) - timedelta(hours=completed) if completed else None,
            **fields,
        )
        task.validate()
        store.save(task)
    # A hand-edited file with an unknown Activity: the app shows it as a General Task, with a warning.
    (folder / f"{PREFIX}99.md").write_text(
        f"---\nid: {PREFIX}99\nstage: inbox\nactivity: juggling\ncreated_at: {start:%Y-%m-%d %H:%M:%S}\n---\n"
        "# Unknown Activity in the file\n\n## Details\n\nShown as a General Task, with a warning in the status bar.\n",
        encoding="utf-8",
    )
    print(f"Wrote {number + 1} test Tasks to {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
