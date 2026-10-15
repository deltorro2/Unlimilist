"""Folded Done: a switch under the Done title folds Done to a narrow strip so Inbox and In Process get its room."""

from datetime import datetime

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QApplication

from unlimilist.board import Board
from unlimilist.domain import Stage
from unlimilist.ui.card import encode_drag
from unlimilist.ui.main_window import MainWindow

STRIP_WIDTH = 90


@pytest.fixture
def board():
    board = Board(clock=lambda: datetime(2026, 10, 12, 9, 0))
    board.add_task("Call grandma about the family recipes")
    board.add_task("Open work", details="- [ ] Not yet")
    busy = board.add_task("Busy")
    board.move_task(busy.id, Stage.IN_PROCESS)
    done = board.add_task("Finished")
    board.move_task(done.id, Stage.DONE)
    return board


@pytest.fixture
def window(qtbot, board):
    window = MainWindow(board)
    qtbot.addWidget(window)
    window.resize(1500, 950)
    window.show()
    qtbot.waitExposed(window)
    return window


def column(window, stage):
    return window.board_view.column_widget(stage)


def widths(window):
    return [column(window, stage).width() for stage in Stage]


def card(window, title):
    return next(c for c in window.board_view.cards() if c.task.title == title)


def fold(qtbot, window, folded=True):
    done = column(window, Stage.DONE)
    if done.is_folded() != folded:
        done.fold_switch.click()
    qtbot.waitUntil(lambda: not done.is_sliding(), timeout=2000)
    QApplication.processEvents()


def drop_on_done(window, task):
    done = column(window, Stage.DONE)
    mime = encode_drag(task)  # must outlive the event
    event = QDropEvent(
        QPointF(done.width() / 2, done.height() - 20),
        Qt.DropAction.MoveAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    done.dropEvent(event)  # Qt only dispatches drop events during a real drag
    QApplication.processEvents()  # drops are handled after the drag loop ends


def test_done_starts_unfolded_with_its_switch_on_under_the_title(window):
    done = column(window, Stage.DONE)

    assert not done.is_folded()
    assert done.fold_switch.isChecked()
    assert done.fold_switch.toolTip() == "Hide Done"
    assert done.fold_switch.y() > done.header.y()


def test_folding_leaves_a_strip_and_inbox_and_in_process_share_its_room(qtbot, window):
    inbox_before, in_process_before, done_before = widths(window)
    card_before = card(window, "Call grandma about the family recipes").width()

    fold(qtbot, window)

    inbox, in_process, done = widths(window)
    assert done == STRIP_WIDTH
    assert abs(inbox - in_process) <= 1
    assert inbox > inbox_before and in_process > in_process_before
    assert card(window, "Call grandma about the family recipes").width() > card_before
    assert not card(window, "Finished").isVisible()
    assert column(window, Stage.DONE).fold_switch.toolTip() == "Show Done"


def test_unfolding_brings_back_the_three_columns(qtbot, window):
    before = widths(window)

    fold(qtbot, window)
    fold(qtbot, window, folded=False)

    assert all(abs(now - then) <= 2 for now, then in zip(widths(window), before))
    assert card(window, "Finished").isVisible()


def test_folding_slides_rather_than_jumps(qtbot, window):
    done = column(window, Stage.DONE)
    start = done.width()

    done.fold_switch.click()
    qtbot.wait(60)

    assert done.is_sliding()
    assert STRIP_WIDTH < done.width() < start


def test_a_task_dropped_on_the_folded_strip_is_done_and_the_strip_flashes(qtbot, window, board):
    fold(qtbot, window)
    task = next(t for t in board.column(Stage.INBOX) if t.title == "Call grandma about the family recipes")

    drop_on_done(window, task)

    assert board.task(task.id).stage == Stage.DONE
    assert column(window, Stage.DONE).is_flashing()
    assert column(window, Stage.DONE).is_folded()


def test_a_refused_drop_on_the_folded_strip_does_not_flash(qtbot, window, board):
    fold(qtbot, window)
    task = next(t for t in board.column(Stage.INBOX) if t.title == "Open work")

    drop_on_done(window, task)

    assert board.task(task.id).stage == Stage.INBOX
    assert not column(window, Stage.DONE).is_flashing()


def test_folding_in_delete_task_mode_unmarks_the_done_tasks(qtbot, window):
    window.delete_action.trigger()
    qtbot.mouseClick(card(window, "Finished"), Qt.MouseButton.LeftButton)
    qtbot.mouseClick(card(window, "Call grandma about the family recipes"), Qt.MouseButton.LeftButton)

    fold(qtbot, window)

    assert [c.task.title for c in window.board_view.cards() if c.is_marked()] == [
        "Call grandma about the family recipes"
    ]
    assert window.in_delete_mode()
