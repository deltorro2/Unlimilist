"""Stale Tasks: a Someday Task that has waited in Inbox or In Process longer than its Stage allows (see CONTEXT.md)."""

from datetime import date, datetime, timedelta

import pytest

from unlimilist.board import Board, InMemoryStore
from unlimilist.domain import Stage, Stale, StaleLimits, Task

LIMITS = StaleLimits(inbox=10, in_process=4)


class Clock:
    """A clock the test sets by hand."""

    def __init__(self, now=datetime(2026, 10, 1, 16, 0)):
        self.now = now

    def __call__(self):
        return self.now

    def go_to(self, day: date, hour: int = 9) -> None:
        self.now = datetime(day.year, day.month, day.day, hour)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def board(clock):
    return Board(clock=clock)


def test_a_new_task_waits_from_when_it_was_made(board, clock):
    task = board.add_task("Buy milk")

    assert task.waiting_since == clock.now


def test_with_11_days_allowed_a_task_from_oct_1_turns_stale_on_oct_13(board, clock):
    task = board.add_task("Buy milk")  # Priority 1 in Inbox: 10 + 1 days

    clock.go_to(date(2026, 10, 12), hour=23)
    assert board.stale(task.id, LIMITS) is None

    clock.go_to(date(2026, 10, 13), hour=0)
    assert board.stale(task.id, LIMITS) == Stale(waited=12, allowed=11)


def test_a_task_lower_in_the_lane_gets_a_day_more_per_rank(board, clock):
    first = board.add_task("First")
    fifth = [board.add_task(f"Task {n}") for n in range(2, 6)][-1]

    clock.go_to(date(2026, 10, 14))  # 13 days after Oct 1

    assert board.stale(first.id, LIMITS) == Stale(waited=13, allowed=11)
    assert board.stale(fifth.id, LIMITS) is None  # 10 + 5 = 15 allowed


def test_in_process_allows_its_own_number_of_days(board, clock):
    task = board.add_task("Write report")
    clock.go_to(date(2026, 10, 2))
    board.move_task(task.id, Stage.IN_PROCESS)

    clock.go_to(date(2026, 10, 7))  # 5 days, In Process allows 4 + 1
    assert board.stale(task.id, LIMITS) is None
    clock.go_to(date(2026, 10, 8))
    assert board.stale(task.id, LIMITS) == Stale(waited=6, allowed=5)


def test_time_limited_and_done_tasks_are_never_stale(board, clock):
    dated = board.add_task("Pay rent", deadline=date(2027, 1, 1))
    done = board.add_task("Old")
    board.move_task(done.id, Stage.DONE)

    clock.go_to(date(2026, 12, 1))

    assert board.stale(dated.id, LIMITS) is None
    assert board.stale(done.id, LIMITS) is None


def test_moving_to_another_stage_restarts_the_clock(board, clock):
    task = board.add_task("Write report")
    clock.go_to(date(2026, 10, 20))

    moved = board.move_task(task.id, Stage.IN_PROCESS)

    assert moved.waiting_since == clock.now
    clock.go_to(date(2026, 10, 21))
    assert board.stale(task.id, LIMITS) is None


def test_dragging_a_task_to_a_new_rank_restarts_only_its_clock(board, clock):
    tasks = [board.add_task(f"Task {n}") for n in range(1, 4)]
    clock.go_to(date(2026, 10, 5))

    board.move_task(tasks[2].id, Stage.INBOX, priority=1)

    assert board.task(tasks[2].id).waiting_since == clock.now
    assert board.task(tasks[0].id).waiting_since == datetime(2026, 10, 1, 16, 0)  # pushed down, not moved
    assert board.task(tasks[1].id).waiting_since == datetime(2026, 10, 1, 16, 0)


def test_dropping_a_task_back_on_its_own_rank_keeps_its_clock(board, clock):
    task = board.add_task("Buy milk")
    board.add_task("Call mom")
    clock.go_to(date(2026, 10, 5))

    board.move_task(task.id, Stage.INBOX, priority=1)

    assert board.task(task.id).waiting_since == datetime(2026, 10, 1, 16, 0)


def test_setting_a_new_priority_in_the_dialog_restarts_the_clock_but_other_edits_do_not(board, clock):
    task = board.add_task("Buy milk")
    board.add_task("Call mom")
    clock.go_to(date(2026, 10, 5))

    board.edit_task(task.id, title="Buy oat milk", priority=1)  # the dialog always sends the shown Priority
    assert board.task(task.id).waiting_since == datetime(2026, 10, 1, 16, 0)

    board.edit_task(task.id, priority=2)
    assert board.task(task.id).waiting_since == clock.now


def test_a_conversion_keeps_the_clock(board, clock):
    task = board.add_task("Buy milk")
    clock.go_to(date(2026, 10, 5))

    board.edit_task(task.id, deadline=date(2026, 12, 1))
    board.edit_task(task.id, deadline=None, priority=1)

    assert board.task(task.id).waiting_since == datetime(2026, 10, 1, 16, 0)


def test_a_duplicate_waits_from_when_it_was_made(board, clock):
    task = board.add_task("Buy milk")
    clock.go_to(date(2026, 10, 5))

    copy = board.duplicate_task(task.id)

    assert copy.waiting_since == clock.now


def test_tasks_from_before_waiting_since_start_from_their_created_date_in_inbox_and_today_in_process(clock):
    created = datetime(2026, 9, 1, 10, 0)
    old = [
        Task(id="a", title="Inbox", stage=Stage.INBOX, created_at=created, priority=1),
        Task(id="b", title="In Process", stage=Stage.IN_PROCESS, created_at=created, priority=1),
        Task(id="c", title="Done", stage=Stage.DONE, created_at=created, completed_at=created),
    ]
    store = InMemoryStore(old)

    board = Board(store, clock=clock)

    assert board.task("a").waiting_since == created
    assert board.task("b").waiting_since == clock.now
    assert {t.id: t.waiting_since for t in store.load_all()}["b"] == clock.now  # kept, so it stays put next time
    assert board.task("c").waiting_since is None


def test_a_task_can_be_stale_in_its_first_load_from_an_old_file(clock):
    old = Task(id="a", title="Inbox", stage=Stage.INBOX, created_at=datetime(2026, 9, 1), priority=1)

    board = Board(InMemoryStore([old]), clock=clock)

    assert board.stale("a", LIMITS) == Stale(waited=30, allowed=11)



def test_the_task_file_keeps_waiting_since(tmp_path, clock):
    from unlimilist.store import MarkdownTaskStore

    task = Board(MarkdownTaskStore(tmp_path), clock=clock).add_task("Buy milk")

    assert "waiting_since: 2026-10-01 16:00:00" in (tmp_path / f"{task.id}.md").read_text()
    assert MarkdownTaskStore(tmp_path).load_all()[0].waiting_since == datetime(2026, 10, 1, 16, 0)


def test_a_task_file_without_waiting_since_still_loads(tmp_path):
    from unlimilist.store import MarkdownTaskStore

    (tmp_path / "old.md").write_text("---\nid: old\nstage: inbox\ncreated_at: 2026-09-01 10:00:00\n---\n# Old\n")

    assert MarkdownTaskStore(tmp_path).load_all()[0].waiting_since is None


# On the Board


@pytest.fixture
def settings_store(tmp_path):
    from unlimilist.settings import SettingsStore

    return SettingsStore(tmp_path / "settings.json")


@pytest.fixture
def window(qtbot, board, clock, settings_store):
    """Two Inbox Tasks from Oct 1 and one In Process Task from Oct 10, seen on Oct 14."""
    from unlimilist.ui.main_window import MainWindow

    board.add_task("Water the plants", details="#home")
    board.add_task("Sort the photos", details="#hobby")
    clock.go_to(date(2026, 10, 10))
    started = board.add_task("Write the report")
    board.move_task(started.id, Stage.IN_PROCESS)
    clock.go_to(date(2026, 10, 14))
    window = MainWindow(board, settings_store=settings_store)
    qtbot.addWidget(window)
    window.resize(1400, 900)
    window.show()
    return window


def card(window, title):
    return next(c for c in window.board_view.cards() if c.task.title == title)


def badge(window, stage):
    return window.board_view.column_widget(stage).stale_badge


def test_a_stale_card_is_faded_with_a_dotted_outline_and_says_why(window):
    stale = card(window, "Water the plants")  # 13 days in Inbox, 11 allowed

    assert stale.is_stale() and stale.is_faded()
    assert stale.toolTip() == "Stale: waiting in Inbox for 13 days (allowed 11)"
    assert card(window, "Sort the photos").toolTip() == "Stale: waiting in Inbox for 13 days (allowed 12)"
    fresh = card(window, "Write the report")  # 4 days In Process, 5 allowed
    assert not fresh.is_stale() and not fresh.is_faded() and fresh.toolTip() == ""


def test_a_stale_card_comes_back_to_full_strength_under_the_pointer(window):
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QEnterEvent
    from PySide6.QtWidgets import QApplication

    stale = card(window, "Water the plants")

    QApplication.sendEvent(stale, QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))
    assert stale.is_stale() and not stale.is_faded()

    QApplication.sendEvent(stale, QEvent(QEvent.Type.Leave))
    assert stale.is_faded()


def test_a_stale_card_selected_for_deleting_shows_only_the_delete_mark(window):
    stale = card(window, "Water the plants")

    stale.set_marked(True)

    assert stale.is_stale() and not stale.is_faded()


def test_each_stage_title_counts_its_stale_tasks_and_hides_the_count_at_zero(window, clock):
    assert badge(window, Stage.INBOX).text() == "2 stale" and not badge(window, Stage.INBOX).isHidden()
    assert badge(window, Stage.IN_PROCESS).isHidden()

    clock.go_to(date(2026, 10, 16))  # the report: 6 days In Process, 5 allowed
    window.refresh()

    assert badge(window, Stage.IN_PROCESS).text() == "1 stale" and not badge(window, Stage.IN_PROCESS).isHidden()
    assert badge(window, Stage.DONE).isHidden()


def test_under_a_tag_filter_the_count_is_of_the_stale_tasks_shown(window):
    window.toggle_tag("home")

    assert badge(window, Stage.INBOX).text() == "1 stale"


def test_turning_stale_marking_off_in_settings_clears_the_look_and_the_counts(window, settings_store, monkeypatch):
    from unlimilist.ui.settings_dialog import SettingsDialog

    def turn_off(dialog):
        dialog.stale_switch.setChecked(False)
        return 0

    monkeypatch.setattr(SettingsDialog, "exec", turn_off)
    window.settings_action.trigger()

    assert not any(c.is_stale() for c in window.board_view.cards())
    assert badge(window, Stage.INBOX).isHidden()
    assert settings_store.load().mark_stale is False


def test_changing_a_stages_days_in_settings_redraws_the_board_and_is_saved(window, settings_store, monkeypatch):
    from unlimilist.ui.settings_dialog import SettingsDialog

    def lengthen(dialog):
        dialog.inbox_days.setValue(12)  # Priority 1 now gets 13 days: just in time
        return 0

    monkeypatch.setattr(SettingsDialog, "exec", lengthen)
    window.settings_action.trigger()

    assert not any(c.is_stale() for c in window.board_view.cards())
    assert badge(window, Stage.INBOX).isHidden()
    assert settings_store.load().stale_inbox_days == 12


def test_the_governance_tab_starts_from_the_saved_settings(qtbot):
    from unlimilist.settings import Settings
    from unlimilist.ui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(Settings(mark_stale=False, stale_inbox_days=20, stale_in_process_days=3))
    qtbot.addWidget(dialog)

    assert [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())] == ["Board view", "Notebook", "Governance"]
    assert not dialog.stale_switch.isChecked()
    assert (dialog.inbox_days.value(), dialog.in_process_days.value()) == (20, 3)
    assert (dialog.inbox_days.minimum(), dialog.inbox_days.maximum()) == (1, 365)
    assert not dialog.inbox_days.isEnabled()  # nothing to set while marking is off
