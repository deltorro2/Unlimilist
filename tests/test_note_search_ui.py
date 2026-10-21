"""The Notebook search (field beside Quick note, two tables, the "Partial match" toast) and Find in Note."""

from datetime import datetime, timedelta

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication

from unlimilist.board import Board
from unlimilist.notebook import Notebook, NoteType
from unlimilist.notebook_password import MemoryVault, NotebookPassword
from unlimilist.ui import password_dialogs
from unlimilist.ui.main_window import MainWindow
from unlimilist.ui.notebook_view import TITLE
from unlimilist.ui.toast import SHOW_MS


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 21, 9, 0)

    def __call__(self):
        self.now += timedelta(minutes=1)
        return self.now


@pytest.fixture
def notebook():
    notebook = Notebook(clock=Clock())
    notebook.create("Trip to Lisbon", "Alfama and tram 28.\nBook the hotel early.\nThe hotel is near the river.")
    notebook.create("Groceries", "milk, bread, Lisbon sardines", tags=("home",))
    notebook.create("Banking", "Call the bank about the card", tags=("finance",))
    notebook.create("Lisbon hotel list", "", tags=("travel",))
    notebook.create("Safe", "the vault code", note_type=NoteType.SECURED, password="s3cret")
    return notebook


@pytest.fixture
def window(qtbot, notebook):
    window = MainWindow(Board(), notebook=notebook, password=NotebookPassword(MemoryVault("s3cret")))
    qtbot.addWidget(window)
    window.resize(1400, 900)
    window.show()
    qtbot.waitExposed(window)
    window.show_notebook()
    return window


def view(window):
    return window.notebook_view


def page(window):
    return window.notebook_view.note_page


def titles(window, ids):
    return [window._notebook.note(i).title for i in ids]


def exact(window):
    return titles(window, view(window).shown_ids()) if view(window).table.isVisible() else []


def partial(window):
    return titles(window, view(window).partial_ids()) if view(window).partial_table.isVisible() else []


def type_search(qtbot, window, text):
    field = view(window).search_field
    field.clear()
    qtbot.keyClicks(field, text)


def search(qtbot, window, text):
    type_search(qtbot, window, text)
    qtbot.keyClick(view(window).search_field, Qt.Key.Key_Return)


def green_text(window):
    field = view(window).search_field
    return [field.text()[start : start + length] for start, length in field.green_ranges()]


# The search field


def test_the_search_field_shares_the_quick_note_line_which_keeps_70_percent(window):
    QApplication.processEvents()
    quick, field = view(window).quick_add, view(window).search_field

    assert quick.y() == field.y()
    assert field.x() > quick.x()
    share = quick.width() / (quick.width() + field.width())
    assert 0.66 < share < 0.74


def test_cmd_f_in_the_table_puts_the_cursor_in_the_search_field(qtbot, window):
    window.activateWindow()
    qtbot.keyClick(window, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)

    qtbot.waitUntil(view(window).search_field.hasFocus)
    assert window.find_shortcut.key() == QKeySequence(QKeySequence.StandardKey.Find)


def test_found_text_turns_green_as_it_is_typed_from_three_characters(qtbot, window):
    type_search(qtbot, window, "li")
    assert green_text(window) == []

    type_search(qtbot, window, "lis")
    assert green_text(window) == ["lis"]

    type_search(qtbot, window, "zzz")
    assert green_text(window) == []


def test_when_the_whole_text_is_not_found_only_the_found_words_turn_green(qtbot, window):
    type_search(qtbot, window, "river sardines nowhere")

    assert green_text(window) == ["river", "sardines"]


def test_typing_alone_does_not_filter(qtbot, window):
    type_search(qtbot, window, "bank")

    assert len(exact(window)) == 5
    assert not view(window).is_searching()


# Enter


def test_enter_lists_the_notes_holding_the_text_in_title_or_body(qtbot, window):
    search(qtbot, window, "LISBON")

    assert set(exact(window)) == {"Trip to Lisbon", "Groceries", "Lisbon hotel list"}
    assert view(window).exact_label.isVisible()
    assert partial(window) == []


def test_a_multi_word_search_lists_exact_matches_above_partial_ones(qtbot, window):
    search(qtbot, window, "lisbon hotel")

    assert exact(window) == ["Lisbon hotel list"]
    assert set(partial(window)) == {"Trip to Lisbon", "Groceries"}
    assert partial(window)[0] == "Trip to Lisbon"  # holds both words
    assert view(window).partial_label.isVisible()
    assert view(window).partial_table.y() > view(window).table.y()
    assert not view(window).toast().isVisible()


def test_with_partial_matches_only_a_partial_match_toast_rises_for_two_seconds(qtbot, window):
    search(qtbot, window, "river sardines nowhere")

    assert exact(window) == []
    assert not view(window).table.isVisible() and not view(window).exact_label.isVisible()
    assert set(partial(window)) == {"Trip to Lisbon", "Groceries"}
    toast = view(window).toast()
    assert toast.isVisible() and toast.text() == "Partial match"
    middle = window.rect().center()
    assert abs(toast.geometry().center().x() - middle.x()) <= 2
    qtbot.waitUntil(lambda: not toast.isVisible(), timeout=SHOW_MS + 1000)


def test_nothing_found_says_so(qtbot, window):
    search(qtbot, window, "zebra")

    assert exact(window) == [] and partial(window) == []
    assert view(window).empty_label.text() == "No Notes match “zebra”."


def test_the_search_and_the_tag_filter_both_apply(qtbot, window):
    window.toggle_tag("travel")
    search(qtbot, window, "lisbon")

    assert exact(window) == ["Lisbon hotel list"]


def test_a_secured_body_is_searched_once_the_password_is_unlocked(qtbot, window, monkeypatch):
    search(qtbot, window, "vault")
    assert exact(window) == []

    monkeypatch.setattr(password_dialogs, "ask_password", lambda parent, accept, **kw: "s3cret" if accept("s3cret") else None)
    view(window).open_note(next(n.id for n in window._notebook.notes() if n.title == "Safe"))
    page(window).back_button.click()

    assert exact(window) == ["Safe"]


# Ending a search


@pytest.mark.parametrize("how", ["escape", "clear button", "empty enter"])
def test_esc_the_clear_button_or_an_empty_enter_ends_the_search(qtbot, window, how):
    search(qtbot, window, "bank")
    assert exact(window) == ["Banking"]
    field = view(window).search_field

    if how == "escape":
        qtbot.keyClick(field, Qt.Key.Key_Escape)
    elif how == "clear button":
        field.clear()  # what the ✕ does
    else:
        field.setText("ba")
        qtbot.keyClick(field, Qt.Key.Key_Return)

    assert len(exact(window)) == 5
    assert field.text() in ("", "ba") and not view(window).is_searching()


def test_the_search_stays_while_a_note_is_open_and_ends_on_tasks_or_a_new_note(qtbot, window):
    search(qtbot, window, "bank")
    view(window).open_note(view(window).shown_ids()[0])
    page(window).back_button.click()
    assert exact(window) == ["Banking"]

    window.show_tasks()
    window.show_notebook()
    assert not view(window).is_searching() and view(window).search_field.text() == ""

    search(qtbot, window, "bank")
    qtbot.keyClicks(view(window).quick_add, "Pay the bank")
    qtbot.keyClick(view(window).quick_add, Qt.Key.Key_Return)
    assert not view(window).is_searching()


def test_a_partial_match_row_opens_its_note(qtbot, window):
    search(qtbot, window, "river sardines nowhere")
    table = view(window).partial_table
    rect = table.visualItemRect(table.item(0, TITLE))

    qtbot.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())

    assert view(window).is_showing_note()


# Find in Note


def open_trip(window):
    view(window).open_note(next(n.id for n in window._notebook.notes() if n.title == "Trip to Lisbon"))


def test_cmd_f_on_a_note_opens_the_find_bar_starting_with_the_search_text(qtbot, window):
    search(qtbot, window, "hotel")
    open_trip(window)

    window.find()

    assert page(window).is_finding()
    assert page(window).find_bar.field.text() == "hotel"
    bar = page(window).find_bar
    assert [bar.next_button.text(), bar.cancel_button.text()] == ["Next", "Cancel"]


def test_next_marks_each_place_in_turn_and_wraps_to_the_top(qtbot, window):
    open_trip(window)
    window.find()
    bar = page(window).find_bar
    qtbot.keyClicks(bar.field, "HOTEL")
    text = page(window).viewer.toPlainText().casefold()
    first, second = text.find("hotel"), text.find("hotel", text.find("hotel") + 1)

    qtbot.keyClick(bar.field, Qt.Key.Key_Return)
    assert page(window).found() == (first, first + 5)
    bar.next_button.click()
    assert page(window).found() == (second, second + 5)
    bar.next_button.click()
    assert page(window).found() == (first, first + 5)
    selections = page(window).viewer.extraSelections()
    assert len(selections) == 1 and selections[0].format.background().color().name() == "#ffe066"


def test_in_edit_mode_find_searches_the_markdown(qtbot, window):
    window._notebook.save(
        next(n.id for n in window._notebook.notes() if n.title == "Groceries"),
        "Groceries",
        "**milk** and milk",
        ("home",),
        NoteType.OPEN,
    )
    view(window).open_note(next(n.id for n in window._notebook.notes() if n.title == "Groceries"))
    page(window).edit_button.click()
    window.find()
    qtbot.keyClicks(page(window).find_bar.field, "**milk")

    page(window).find_next()

    assert page(window).found() == (0, 6)
    assert page(window).editor.extraSelections()


def test_text_that_is_not_there_turns_the_field_red(qtbot, window):
    open_trip(window)
    window.find()
    qtbot.keyClicks(page(window).find_bar.field, "zebra")

    assert not page(window).find_next()

    assert page(window).find_bar.field.property("notFound")
    assert page(window).found() is None


def test_esc_or_cancel_closes_the_find_bar_and_clears_the_mark(qtbot, window):
    open_trip(window)
    window.find()
    qtbot.keyClicks(page(window).find_bar.field, "hotel")
    page(window).find_next()

    qtbot.keyClick(page(window).find_bar.field, Qt.Key.Key_Escape)

    assert not page(window).is_finding()
    assert page(window).viewer.extraSelections() == []
    window.find()
    page(window).find_bar.cancel_button.click()
    assert not page(window).is_finding()


def test_cmd_f_does_nothing_on_the_board(qtbot, window):
    window.show_tasks()

    window.find()

    assert not view(window).search_field.hasFocus()


def test_a_new_search_or_opening_a_note_dismisses_the_partial_match_toast(qtbot, window):
    search(qtbot, window, "river sardines nowhere")
    assert view(window).toast().isVisible()

    search(qtbot, window, "bank")
    assert not view(window).toast().isVisible()

    search(qtbot, window, "river sardines nowhere")
    view(window).open_note(view(window).partial_ids()[0])
    assert not view(window).toast().isVisible()
