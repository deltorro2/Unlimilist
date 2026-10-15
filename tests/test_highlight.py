"""After a Task is created or moved, the Board shows where it landed: its Column jumps to it if it is out of
view, and the card flashes yellow, then fades back to its own shade."""

from datetime import date, datetime

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox

from unlimilist.board import Board
from unlimilist.domain import LaneKind, Stage
from unlimilist.ui.main_window import MainWindow
from unlimilist.ui.task_dialog import TaskDialog

LONG_INBOX = 30  # enough Someday Tasks that the bottom of the Inbox is out of view


@pytest.fixture
def board():
    board = Board(clock=lambda: datetime(2026, 10, 12, 9, 0))
    for n in range(LONG_INBOX):
        board.add_task(f"Someday {n + 1}")
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


def fully_in_view(card) -> bool:
    return card.visibleRegion().boundingRect().contains(card.rect())  # the region also takes in the shadow


def highlighted(window) -> list[str]:
    return [c.task.title for c in window.board_view.cards() if c.is_highlighted()]


def test_a_quick_added_task_below_the_fold_is_scrolled_into_view_and_highlighted(qtbot, window):
    assert not fully_in_view(card(window, f"Someday {LONG_INBOX}"))

    window.board_view.quick_add.setText("Fresh")
    qtbot.keyClick(window.board_view.quick_add, Qt.Key.Key_Return)

    qtbot.waitUntil(lambda: fully_in_view(card(window, "Fresh")), timeout=500)
    assert highlighted(window) == ["Fresh"]


def test_the_highlight_is_yellow_with_dark_ink_holds_then_fades_back_to_the_cards_own_shade(qtbot, window):
    top = card(window, "Someday 1")  # the darkest card, with white ink
    shade, ink = top.fill(), top.ink()
    assert ink == "#ffffff"

    top.highlight()

    assert top.shown_fill() == "#ffe066"
    assert top.ink() == "#1b1b1f"
    qtbot.wait(800)
    assert top.shown_fill() == "#ffe066"  # still holding
    qtbot.waitUntil(lambda: not top.is_highlighted(), timeout=1000)
    assert (top.shown_fill(), top.ink()) == (shade, ink)


def test_a_card_already_in_view_is_highlighted_without_scrolling(qtbot, window, board):
    column = window.board_view.column_widget(Stage.INBOX)
    second = board.lane(Stage.INBOX, LaneKind.SOMEDAY)[1]

    window.handle_drop(second.id, Stage.INBOX, LaneKind.SOMEDAY, 0)  # to the top

    qtbot.wait(50)
    assert column.scroll_position() == 0
    assert highlighted(window) == [second.title]


def test_only_one_card_is_highlighted_at_a_time(qtbot, window):
    card(window, "Someday 1").highlight()

    window.board_view.highlight(card(window, "Someday 2").task.id)

    assert highlighted(window) == ["Someday 2"]


def dialog_answers(monkeypatch, fill):
    """Every TaskDialog runs `fill` on itself instead of waiting for the user; `fill` returns the result."""
    monkeypatch.setattr(TaskDialog, "exec", fill)


def save_with(**edits):
    def fill(dialog):
        for name, value in edits.items():
            if name == "title":
                dialog.title_edit.setText(value)
            elif name == "deadline":
                dialog.deadline_field.set_date(value)
            elif name == "priority":
                dialog.priority_spin.setValue(value)
        dialog.save_button.click()
        return dialog.result()

    return fill


def test_a_task_from_the_new_task_dialog_is_highlighted(qtbot, window, monkeypatch):
    dialog_answers(monkeypatch, save_with(title="From the dialog"))

    window.new_task()

    qtbot.waitUntil(lambda: fully_in_view(card(window, "From the dialog")), timeout=500)
    assert highlighted(window) == ["From the dialog"]


def test_a_duplicate_is_highlighted_not_its_original(window):
    menu = window.card_menu(card(window, "Someday 1").task.id)

    next(a for a in menu.actions() if a.text() == "Duplicate Task").trigger()

    assert highlighted(window) == ["[Duplication] Someday 1"]


def test_a_task_dropped_on_another_stage_is_highlighted_there(window, board):
    task = board.lane(Stage.INBOX, LaneKind.SOMEDAY)[3]

    window.handle_drop(task.id, Stage.IN_PROCESS, LaneKind.SOMEDAY, 0)

    assert [c.task.title for c in window.board_view.column_widget(Stage.IN_PROCESS).cards() if c.is_highlighted()] == [
        task.title
    ]


def test_a_refused_drop_on_done_is_not_highlighted(window, board):
    task = board.add_task("Open work", details="- [ ] Not yet")

    window.handle_drop(task.id, Stage.DONE, None, 0)

    assert highlighted(window) == []


def test_a_cancelled_conversion_is_not_highlighted(window, board, monkeypatch):
    dialog_answers(monkeypatch, lambda dialog: QDialog.DialogCode.Rejected)
    task = board.lane(Stage.INBOX, LaneKind.SOMEDAY)[0]

    window.handle_drop(task.id, Stage.INBOX, LaneKind.TIME_LIMITED, 0)

    assert highlighted(window) == []


def test_a_conversion_to_someday_is_highlighted(window, board, monkeypatch):
    task = board.add_task("Dated", deadline=date(2026, 12, 1))
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)

    window.handle_drop(task.id, Stage.INBOX, LaneKind.SOMEDAY, 2)

    assert highlighted(window) == ["Dated"]


def test_an_edit_that_moves_the_task_is_highlighted(window, board, monkeypatch):
    dialog_answers(monkeypatch, save_with(priority=999))  # to the bottom

    window.open_task(board.lane(Stage.INBOX, LaneKind.SOMEDAY)[0].id)

    assert highlighted(window) == ["Someday 1"]


def test_an_edit_that_leaves_the_task_in_place_is_not_highlighted(window, board, monkeypatch):
    dialog_answers(monkeypatch, save_with(title="Renamed"))

    window.open_task(board.lane(Stage.INBOX, LaneKind.SOMEDAY)[0].id)

    assert highlighted(window) == []
    assert card(window, "Renamed")
