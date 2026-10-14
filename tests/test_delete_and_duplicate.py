"""Delete Task mode, the cards' context menus, and duplicating Inbox Tasks."""

from datetime import datetime

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from unlimilist.board import Board
from unlimilist.domain import LaneKind, Stage
from unlimilist.ui.main_window import MainWindow
from unlimilist.ui.task_dialog import TaskDialog


@pytest.fixture
def board():
    board = Board(clock=lambda: datetime(2026, 10, 12, 9, 0))
    board.add_task("A", details="#work")
    board.add_task("B")
    busy = board.add_task("Busy")
    board.move_task(busy.id, Stage.IN_PROCESS)
    done = board.add_task("Done one")
    board.move_task(done.id, Stage.DONE)
    return board


@pytest.fixture
def window(qtbot, board):
    window = MainWindow(board)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    return window


def card(window, title):
    for stage in Stage:
        for c in window.board_view.column_widget(stage).cards():
            if c.task.title == title:
                return c
    raise LookupError(title)


def titles(board, stage):
    if stage == Stage.DONE:
        return [t.title for t in board.lane(Stage.DONE)]
    return [t.title for t in board.lane(stage, LaneKind.SOMEDAY)]


def click(qtbot, window, title):
    qtbot.mouseClick(card(window, title), Qt.MouseButton.LeftButton)


@pytest.fixture
def answer(monkeypatch):
    """Answers the delete warning; `asked` records each question."""

    class Answer:
        reply = QMessageBox.StandardButton.Yes
        asked: list[str] = []

    answer = Answer()
    answer.asked = []

    def warning(parent, title, text, buttons=None, default=None):
        answer.asked.append(text)
        return answer.reply

    monkeypatch.setattr(QMessageBox, "warning", warning)
    return answer


def test_the_delete_task_button_starts_a_mode_that_locks_everything_else(qtbot, window):
    assert window.delete_action.text() == "Delete Task"

    window.delete_action.trigger()

    assert window.delete_action.text() == "Select Tasks in Inbox or Done"
    assert window.in_delete_mode()
    assert not window.new_task_action.isEnabled()
    assert not window.sidebar.isEnabled()
    assert not window.board_view.quick_add.isEnabled()
    assert window.board_view.cursor().shape() == Qt.CursorShape.CrossCursor


def test_clicking_inbox_and_done_tasks_selects_and_unselects_them_but_not_in_process(qtbot, window, monkeypatch):
    opened = []
    monkeypatch.setattr(TaskDialog, "exec", lambda dialog: opened.append(dialog) or 0)
    window.delete_action.trigger()

    click(qtbot, window, "A")
    click(qtbot, window, "Done one")
    click(qtbot, window, "Busy")
    click(qtbot, window, "B")
    click(qtbot, window, "B")

    assert {title: card(window, title).is_marked() for title in ("A", "B", "Busy", "Done one")} == {
        "A": True,
        "B": False,
        "Busy": False,
        "Done one": True,
    }
    assert window.delete_action.text() == "Delete"
    assert card(window, "Busy").cursor().shape() == Qt.CursorShape.ForbiddenCursor
    assert opened == []  # clicking selects; it never opens a Task
    assert not card(window, "A").draggable()


def test_delete_asks_first_and_yes_deletes_the_selected_tasks(qtbot, window, board, answer):
    window.delete_action.trigger()
    click(qtbot, window, "A")
    click(qtbot, window, "Done one")

    window.delete_action.trigger()

    assert answer.asked == ["Are you sure you want to delete 2 Tasks?"]
    assert titles(board, Stage.INBOX) == ["B"]
    assert titles(board, Stage.DONE) == []
    assert [c.task.title for c in window.board_view.column_widget(Stage.INBOX).cards()] == ["B"]
    assert not window.in_delete_mode()
    assert window.delete_action.text() == "Delete Task"
    assert window.sidebar.isEnabled() and window.new_task_action.isEnabled()


def test_answering_no_keeps_the_mode_and_the_selection(qtbot, window, board, answer):
    answer.reply = QMessageBox.StandardButton.No
    window.delete_action.trigger()
    click(qtbot, window, "A")

    window.delete_action.trigger()

    assert answer.asked == ["Are you sure you want to delete 1 Task?"]
    assert titles(board, Stage.INBOX) == ["A", "B"]
    assert window.in_delete_mode()
    assert card(window, "A").is_marked()


def test_escape_leaves_the_mode_and_clears_the_selection(qtbot, window):
    window.delete_action.trigger()
    click(qtbot, window, "A")

    qtbot.keyClick(window, Qt.Key.Key_Escape)

    assert not window.in_delete_mode()
    assert not card(window, "A").is_marked()
    assert window.delete_action.text() == "Delete Task"


def test_pressing_the_button_again_before_selecting_leaves_the_mode(qtbot, window, answer):
    window.delete_action.trigger()

    window.delete_action.trigger()

    assert not window.in_delete_mode()
    assert answer.asked == []


def test_the_context_menu_offers_duplicate_and_delete_in_inbox_delete_in_done_and_nothing_in_process(window):
    def menu(title):
        built = window.card_menu(card(window, title).task.id)
        return None if built is None else [a.text() for a in built.actions()]

    assert menu("A") == ["Duplicate Task", "Delete Task"]
    assert menu("Done one") == ["Delete Task"]
    assert menu("Busy") is None


def test_delete_task_in_the_context_menu_asks_and_deletes_that_task(window, board, answer):
    menu = window.card_menu(card(window, "Done one").task.id)

    next(a for a in menu.actions() if a.text() == "Delete Task").trigger()

    assert answer.asked == ["Are you sure you want to delete 1 Task?"]
    assert titles(board, Stage.DONE) == []


def test_duplicate_task_adds_the_copy_right_below_and_clears_the_tag_filter(qtbot, window, board):
    window.toggle_tag("work")
    menu = window.card_menu(card(window, "A").task.id)

    next(a for a in menu.actions() if a.text() == "Duplicate Task").trigger()

    assert titles(board, Stage.INBOX) == ["A", "[Duplication] A", "B"]
    assert not window.sidebar.clear_button.isEnabled()  # the filter was cleared, as for any new Task
    assert [c.task.title for c in window.board_view.column_widget(Stage.INBOX).cards()] == ["A", "[Duplication] A", "B"]
