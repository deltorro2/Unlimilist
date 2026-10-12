from datetime import date, datetime, timedelta

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from unlimilist.board import Board
from unlimilist.domain import LaneKind, Stage
from unlimilist.ui.card import encode_drag
from unlimilist.ui.main_window import MainWindow
from unlimilist.ui.task_dialog import TaskDialog


@pytest.fixture
def board():
    return Board(clock=lambda: datetime(2026, 10, 12, 9, 0))


def test_task_dialog_will_not_save_without_a_title(qtbot, board):
    dialog = TaskDialog(board)
    qtbot.addWidget(dialog)

    dialog.save_button.click()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "Title" in dialog.error_label.text()
    assert board.lane(Stage.INBOX, LaneKind.SOMEDAY) == []

    dialog.title_edit.setText("Buy milk")
    dialog.save_button.click()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert [t.title for t in board.lane(Stage.INBOX, LaneKind.SOMEDAY)] == ["Buy milk"]


def test_priority_field_is_offered_only_while_both_dates_are_empty(qtbot, board):
    board.add_task("A")
    board.add_task("B")
    dialog = TaskDialog(board)
    qtbot.addWidget(dialog)

    assert not dialog.priority_spin.isHidden()
    assert dialog.priority_spin.value() == 3  # the bottom of the Lane

    dialog.deadline_field.set_date(date(2026, 10, 31))
    assert dialog.priority_spin.isHidden()

    dialog.deadline_field.set_date(None)
    assert not dialog.priority_spin.isHidden()


def test_saving_a_new_task_with_priority_one_puts_it_on_top(qtbot, board):
    board.add_task("A")
    dialog = TaskDialog(board)
    qtbot.addWidget(dialog)

    dialog.title_edit.setText("Urgent")
    dialog.priority_spin.setValue(1)
    dialog.save_button.click()

    assert [t.title for t in board.lane(Stage.INBOX, LaneKind.SOMEDAY)] == ["Urgent", "A"]


def test_editing_shows_the_current_priority(qtbot, board):
    board.add_task("A")
    b = board.add_task("B")

    dialog = TaskDialog(board, board.task(b.id))
    qtbot.addWidget(dialog)

    assert dialog.priority_spin.value() == 2
    assert dialog.priority_spin.maximum() == 2


@pytest.mark.parametrize(("answer", "remaining"), [(QMessageBox.StandardButton.No, ["A"]), (QMessageBox.StandardButton.Yes, [])])
def test_delete_removes_the_task_only_after_confirmation(qtbot, board, monkeypatch, answer, remaining):
    a = board.add_task("A")
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: answer)
    dialog = TaskDialog(board, board.task(a.id))
    qtbot.addWidget(dialog)

    dialog.delete_button.click()

    assert [t.title for t in board.lane(Stage.INBOX, LaneKind.SOMEDAY)] == remaining


def test_new_task_dialog_has_no_delete_button(qtbot, board):
    dialog = TaskDialog(board)
    qtbot.addWidget(dialog)

    assert dialog.delete_button.isHidden()


def card_titles(window, stage, kind=None):
    return [card.title_label.text() for card in window.board_view.lane_widget(stage, kind).cards()]


def test_quick_add_puts_a_task_at_the_bottom_of_inbox_someday(qtbot, board):
    board.add_task("A")
    window = MainWindow(board)
    qtbot.addWidget(window)

    qtbot.keyClicks(window.board_view.quick_add, "Buy milk")
    qtbot.keyClick(window.board_view.quick_add, Qt.Key.Key_Return)

    assert card_titles(window, Stage.INBOX, LaneKind.SOMEDAY) == ["1. A", "2. Buy milk"]
    assert window.board_view.quick_add.text() == ""


@pytest.fixture
def window(qtbot, board):
    window = MainWindow(board)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    return window


def drop_on_lane(window, task, stage, kind=None, at_top=False):
    lane = window.board_view.lane_widget(stage, kind)
    y = 40 if at_top else lane.height() - 5
    mime = encode_drag(task)  # must outlive the event
    event = QDropEvent(
        QPointF(lane.width() / 2, y),
        Qt.DropAction.MoveAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    lane.dropEvent(event)  # Qt only dispatches drop events during a real drag
    QApplication.processEvents()  # drops are handled after the drag loop ends


def test_dropping_a_card_in_another_stage_moves_it(window, board):
    a = board.add_task("A")
    window.board_view.refresh()

    drop_on_lane(window, board.task(a.id), Stage.DONE)

    assert card_titles(window, Stage.DONE) == ["A"]
    assert card_titles(window, Stage.INBOX, LaneKind.SOMEDAY) == []


def test_time_limited_card_shows_its_dates_as_day_month_year(window, board):
    board.add_task("Trip", due_date=date(2026, 11, 3), deadline=date(2026, 11, 9))
    window.board_view.refresh()

    card = window.board_view.lane_widget(Stage.INBOX, LaneKind.TIME_LIMITED).cards()[0]

    assert "03/11/2026" in card.meta_label.text()
    assert "09/11/2026" in card.meta_label.text()


def test_dropping_time_limited_on_someday_clears_dates_after_confirmation(window, board, monkeypatch):
    board.add_task("A")
    board.move_task(board.lane(Stage.INBOX, LaneKind.SOMEDAY)[0].id, Stage.IN_PROCESS)
    rent = board.add_task("Pay rent", deadline=date(2026, 10, 31))
    window.board_view.refresh()
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

    drop_on_lane(window, board.task(rent.id), Stage.IN_PROCESS, LaneKind.SOMEDAY, at_top=True)

    assert card_titles(window, Stage.IN_PROCESS, LaneKind.SOMEDAY) == ["1. Pay rent", "2. A"]
    assert board.task(rent.id).deadline is None


def test_dropping_someday_on_time_limited_asks_for_a_date_and_cancel_keeps_it(window, board, monkeypatch):
    a = board.add_task("A")
    window.board_view.refresh()
    monkeypatch.setattr(TaskDialog, "exec", lambda self: QDialog.DialogCode.Rejected)

    drop_on_lane(window, board.task(a.id), Stage.IN_PROCESS, LaneKind.TIME_LIMITED)

    assert card_titles(window, Stage.INBOX, LaneKind.SOMEDAY) == ["1. A"]
    assert card_titles(window, Stage.IN_PROCESS, LaneKind.TIME_LIMITED) == []


def test_dropping_someday_on_time_limited_moves_it_once_a_date_is_added(window, board, monkeypatch):
    a = board.add_task("A")
    window.board_view.refresh()

    def add_a_deadline(dialog):
        dialog.save_button.click()  # no date yet: refused
        assert "date" in dialog.error_label.text()
        dialog.deadline_field.set_date(date(2026, 11, 1))
        dialog.save_button.click()
        return dialog.result()

    monkeypatch.setattr(TaskDialog, "exec", add_a_deadline)

    drop_on_lane(window, board.task(a.id), Stage.IN_PROCESS, LaneKind.TIME_LIMITED)

    assert card_titles(window, Stage.IN_PROCESS, LaneKind.TIME_LIMITED) == ["A"]
    assert card_titles(window, Stage.INBOX, LaneKind.SOMEDAY) == []
