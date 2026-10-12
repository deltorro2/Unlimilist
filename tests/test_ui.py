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


def test_priority_is_locked_while_a_date_is_set(qtbot, board):
    board.add_task("A")
    board.add_task("B")
    dialog = TaskDialog(board)
    qtbot.addWidget(dialog)

    assert dialog.priority_spin.isEnabled()
    assert dialog.priority_spin.value() == 999  # the bottom of the Lane
    assert dialog.priority_note.isHidden()

    dialog.deadline_field.set_date(date(2026, 10, 31))
    assert not dialog.priority_spin.isEnabled()
    assert not dialog.priority_note.isHidden()
    assert "due date or deadline" in dialog.priority_note.text()

    dialog.deadline_field.set_date(None)
    assert dialog.priority_spin.isEnabled()


def test_saving_a_new_task_with_the_default_priority_puts_it_at_the_bottom(qtbot, board):
    board.add_task("A")
    dialog = TaskDialog(board)
    qtbot.addWidget(dialog)

    dialog.title_edit.setText("B")
    dialog.save_button.click()

    lane = board.lane(Stage.INBOX, LaneKind.SOMEDAY)
    assert [(t.title, t.priority) for t in lane] == [("A", 1), ("B", 2)]


def test_priority_is_locked_for_a_done_task(qtbot, board):
    a = board.add_task("A")
    board.move_task(a.id, Stage.DONE)

    dialog = TaskDialog(board, board.task(a.id))
    qtbot.addWidget(dialog)

    assert not dialog.priority_spin.isEnabled()
    assert "Done" in dialog.priority_note.text()


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


def column_cards(window, stage, kind=None):
    cards = window.board_view.column_widget(stage).cards()
    return [c for c in cards if kind is None or c.task.kind == kind]


def card_titles(window, stage, kind=None):
    return [card.title_label.text() for card in column_cards(window, stage, kind)]


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


def drop_on_column(window, task, stage, side=LaneKind.SOMEDAY, at_top=False):
    """Drop `task` on the Someday (left) or Time-limited (right) side of a Stage's Column."""
    column = window.board_view.column_widget(stage)
    x = column.width() * (0.2 if side == LaneKind.SOMEDAY else 0.8)
    y = 60 if at_top else column.height() - 5
    mime = encode_drag(task)  # must outlive the event
    event = QDropEvent(
        QPointF(x, y),
        Qt.DropAction.MoveAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    column.dropEvent(event)  # Qt only dispatches drop events during a real drag
    QApplication.processEvents()  # drops are handled after the drag loop ends


def test_column_shows_the_interleaved_order(window, board):
    for n in range(1, 7):
        board.add_task(f"S{n}")
    board.add_task("T1", deadline=date(2026, 11, 1))
    board.add_task("T2", deadline=date(2026, 11, 2))
    window.board_view.refresh()

    titles = [c.task.title for c in column_cards(window, Stage.INBOX)]

    assert titles == ["T1", "S1", "S2", "S3", "S4", "S5", "T2", "S6"]


def test_someday_cards_align_left_and_time_limited_cards_align_right(window, board):
    board.add_task("S")
    board.add_task("T", deadline=date(2026, 11, 1))
    window.board_view.refresh()
    QApplication.processEvents()

    someday = column_cards(window, Stage.INBOX, LaneKind.SOMEDAY)[0]
    time_limited = column_cards(window, Stage.INBOX, LaneKind.TIME_LIMITED)[0]
    full_width = time_limited.geometry().right() - someday.geometry().left()

    assert someday.geometry().left() < time_limited.geometry().left()
    assert someday.width() == pytest.approx(0.75 * full_width, abs=3)
    assert time_limited.width() == pytest.approx(0.75 * full_width, abs=3)


def test_done_column_is_narrower(window):
    QApplication.processEvents()
    inbox = window.board_view.column_widget(Stage.INBOX).width()
    done = window.board_view.column_widget(Stage.DONE).width()

    assert done == pytest.approx(0.6 * inbox, rel=0.05)


def test_card_previews_details_as_plain_text(window, board):
    board.add_task("Groceries", details="**Oat** milk and _bread_\n\n- eggs")
    window.board_view.refresh()

    card = column_cards(window, Stage.INBOX)[0]

    assert card.details_label.text().startswith("Oat milk and bread")
    assert "*" not in card.details_label.text()
    assert card.meta_label.isHidden()  # Someday cards have no dates line


def test_time_limited_card_shows_its_dates_as_day_month_year(window, board):
    board.add_task("Trip", due_date=date(2026, 11, 3), deadline=date(2026, 11, 9))
    window.board_view.refresh()

    card = column_cards(window, Stage.INBOX, LaneKind.TIME_LIMITED)[0]

    assert "03/11/2026" in card.meta_label.text()
    assert "09/11/2026" in card.meta_label.text()


def test_done_card_title_is_struck_through(window, board):
    a = board.add_task("A", details="notes")
    board.move_task(a.id, Stage.DONE)
    window.board_view.refresh()

    card = column_cards(window, Stage.DONE)[0]

    assert card.title_label.font().strikeOut()
    assert card.details_label.isHidden()


def test_dropping_a_card_in_another_stage_moves_it(window, board):
    a = board.add_task("A")
    window.board_view.refresh()

    drop_on_column(window, board.task(a.id), Stage.DONE)

    assert card_titles(window, Stage.DONE) == ["A"]
    assert card_titles(window, Stage.INBOX) == []


def test_dropping_on_the_someday_side_ranks_among_someday_cards(window, board):
    board.add_task("A")
    board.add_task("B")
    board.add_task("T", deadline=date(2026, 11, 1))
    c = board.add_task("C")
    window.board_view.refresh()

    drop_on_column(window, board.task(c.id), Stage.INBOX, LaneKind.SOMEDAY, at_top=True)

    assert card_titles(window, Stage.INBOX, LaneKind.SOMEDAY) == ["1. C", "2. A", "3. B"]


def test_dropping_time_limited_on_the_someday_side_clears_dates_after_confirmation(window, board, monkeypatch):
    a = board.add_task("A")
    board.move_task(a.id, Stage.IN_PROCESS)
    rent = board.add_task("Pay rent", deadline=date(2026, 10, 31))
    window.board_view.refresh()
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

    drop_on_column(window, board.task(rent.id), Stage.IN_PROCESS, LaneKind.SOMEDAY, at_top=True)

    assert card_titles(window, Stage.IN_PROCESS, LaneKind.SOMEDAY) == ["1. Pay rent", "2. A"]
    assert board.task(rent.id).deadline is None


def test_dropping_someday_on_the_time_limited_side_asks_for_a_date_and_cancel_keeps_it(window, board, monkeypatch):
    a = board.add_task("A")
    window.board_view.refresh()
    monkeypatch.setattr(TaskDialog, "exec", lambda self: QDialog.DialogCode.Rejected)

    drop_on_column(window, board.task(a.id), Stage.IN_PROCESS, LaneKind.TIME_LIMITED)

    assert card_titles(window, Stage.INBOX, LaneKind.SOMEDAY) == ["1. A"]
    assert card_titles(window, Stage.IN_PROCESS) == []


def test_dropping_someday_on_the_time_limited_side_moves_it_once_a_date_is_added(window, board, monkeypatch):
    a = board.add_task("A")
    window.board_view.refresh()

    def add_a_deadline(dialog):
        dialog.save_button.click()  # no date yet: refused
        assert "date" in dialog.error_label.text()
        dialog.deadline_field.set_date(date(2026, 11, 1))
        dialog.save_button.click()
        return dialog.result()

    monkeypatch.setattr(TaskDialog, "exec", add_a_deadline)

    drop_on_column(window, board.task(a.id), Stage.IN_PROCESS, LaneKind.TIME_LIMITED)

    assert card_titles(window, Stage.IN_PROCESS, LaneKind.TIME_LIMITED) == ["A"]
    assert card_titles(window, Stage.INBOX) == []
