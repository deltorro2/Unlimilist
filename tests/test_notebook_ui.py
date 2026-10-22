"""The Notebook view: the table of Notes, Show Note, Tags, Secured Notes, deleting and importing."""

from datetime import datetime, timedelta

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from conftest import rendered_text
from unlimilist.board import Board
from unlimilist.note_store import MarkdownNoteStore
from unlimilist.notebook import Notebook, NoteType
from unlimilist.notebook_password import MemoryVault, NotebookPassword
from unlimilist.ui import password_dialogs
from unlimilist.ui.main_window import MainWindow
from unlimilist.ui.note_page import AUTOSAVE_MS
from unlimilist.ui.notebook_view import CREATED, OPENED, SIZE, TITLE, TYPE

START = datetime(2026, 10, 21, 9, 0)


class Clock:
    def __init__(self):
        self.now = START

    def __call__(self):
        self.now += timedelta(minutes=1)  # every Note gets its own minute
        return self.now


@pytest.fixture
def board():
    board = Board(clock=lambda: START)
    board.add_task("Plan the trip", details="#travel #work")
    return board


@pytest.fixture
def notebook(tmp_path):
    notebook = Notebook(MarkdownNoteStore(tmp_path / "notes"), clock=Clock())
    notebook.create("Lisbon", "# Day 1\n\nAlfama and **tram 28**", tags=("travel", "family"))
    notebook.create("Groceries", "- milk\n- bread", tags=("home",))
    notebook.create("Bank", "PIN 1234", tags=("finance",), note_type=NoteType.SECURED, password="s3cret")
    return notebook


@pytest.fixture
def vault():
    return MemoryVault("s3cret")


@pytest.fixture
def window(qtbot, board, notebook, vault):
    window = MainWindow(board, notebook=notebook, password=NotebookPassword(vault))
    qtbot.addWidget(window)
    window.resize(1400, 900)
    window.show()
    qtbot.waitExposed(window)
    window.show_notebook()
    return window


@pytest.fixture
def asked(monkeypatch):
    """Answers the password dialog with the queued passwords (None = Cancel) and records each time it opened."""
    answers, calls = [], []

    def ask(parent, accept, title="", message=""):
        calls.append(title)
        while answers:
            typed = answers.pop(0)
            if typed is None:
                return None
            if accept(typed):
                return typed
        return None

    monkeypatch.setattr(password_dialogs, "ask_password", ask)
    return answers, calls


def view(window):
    return window.notebook_view


def page(window):
    return window.notebook_view.note_page


def titles(window):
    return [view(window).row_texts(i)[TITLE] for i in view(window).shown_ids()]


def note_id(window, title):
    return next(n.id for n in window._notebook.notes() if n.title == title)


def click_row(qtbot, window, title):
    table = view(window).table
    row = titles(window).index(title)
    rect = table.visualItemRect(table.item(row, CREATED))
    qtbot.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())


# Switching views


def test_the_notebook_item_shows_the_notebook_and_its_own_buttons(qtbot, window):
    assert window.current_view() == "notebook"
    assert window.new_note_action.isVisible() and window.import_action.isVisible()
    assert not window.new_task_action.isVisible() and not window.delete_action.isVisible()
    assert window.new_note_action.text() == "＋ New Note"

    views = window.sidebar.views
    qtbot.mouseClick(views.viewport(), Qt.MouseButton.LeftButton, pos=views.visualItemRect(views.item(0)).center())

    assert window.current_view() == "tasks"
    assert window.new_task_action.isVisible() and not window.new_note_action.isVisible()


def test_only_the_view_on_screen_has_its_new_button_on_so_cmd_n_is_unambiguous(window):
    assert window.new_note_action.isEnabled() and not window.new_task_action.isEnabled()

    window.show_tasks()

    assert window.new_task_action.isEnabled() and not window.new_note_action.isEnabled()
    assert not window.import_action.isEnabled()


def test_the_app_starts_on_tasks(qtbot, board):
    window = MainWindow(board)
    qtbot.addWidget(window)

    assert window.current_view() == "tasks"


# The table


def test_the_table_lists_every_note_newest_first_with_its_columns(window, notebook):
    assert titles(window) == ["Bank", "Groceries", "Lisbon"]
    headers = [view(window).table.horizontalHeaderItem(c).text() for c in range(5)]
    assert headers == ["Title", "Created", "Last opened", "Type", "Size"]
    lisbon = view(window).row_texts(note_id(window, "Lisbon"))
    assert lisbon[CREATED] == "21 Oct 2026, 09:01"
    assert lisbon[OPENED] == "—"
    assert lisbon[SIZE] == f"{len('# Day 1') + len(chr(10) * 2) + len('Alfama and **tram 28**')} B"
    table = view(window).table
    assert table.item(titles(window).index("Bank"), TYPE).toolTip() == "Secured"
    assert table.item(titles(window).index("Lisbon"), TYPE).toolTip() == "Open"


def test_opening_a_note_moves_it_to_the_top(qtbot, window):
    click_row(qtbot, window, "Lisbon")
    page(window).back_button.click()

    assert titles(window)[0] == "Lisbon"
    assert view(window).row_texts(note_id(window, "Lisbon"))[OPENED] != "—"


def test_clicking_a_header_sorts_and_clicking_again_turns_the_order_around(window):
    view(window).sort_by(TITLE)
    assert titles(window) == ["Bank", "Groceries", "Lisbon"]

    view(window).sort_by(TITLE)
    assert titles(window) == ["Lisbon", "Groceries", "Bank"]

    view(window).sort_by(TYPE)
    assert titles(window)[-1] == "Bank"


def test_sizes_read_as_bytes_kilobytes_and_megabytes():
    from unlimilist.ui.notebook_view import format_size

    assert [format_size(n) for n in (820, 14 * 1024, int(1.2 * 1024 * 1024))] == ["820 B", "14 KB", "1.2 MB"]


# Quick add


def test_quick_add_makes_a_note_highlights_it_and_stays_in_the_table(qtbot, window):
    text = "Remember to ask the landlord about the heating, the leaking tap in the kitchen and the parking permit"
    qtbot.keyClicks(view(window).quick_add, text)
    qtbot.keyClick(view(window).quick_add, Qt.Key.Key_Return)

    new = window._notebook.notes()[0]
    assert new.body == text
    assert len(new.title) <= 80 and new.title.endswith("…")
    assert titles(window)[0] == new.title
    assert view(window).is_highlighted(new.id)
    assert view(window).is_showing_table()
    assert view(window).quick_add.text() == ""


def test_creating_a_note_clears_the_tag_filter(qtbot, window):
    window.toggle_tag("home")
    assert titles(window) == ["Groceries"]

    qtbot.keyClicks(view(window).quick_add, "Call the plumber")
    qtbot.keyClick(view(window).quick_add, Qt.Key.Key_Return)

    assert len(titles(window)) == 4


# Show Note


def test_a_clicked_note_opens_in_view_mode_rendered(qtbot, window):
    click_row(qtbot, window, "Lisbon")

    assert view(window).is_showing_note()
    assert not page(window).is_editing()
    assert page(window).title_edit.text() == "Lisbon"
    assert page(window).title_edit.isReadOnly()
    assert page(window).viewer.isVisible() and not page(window).editor.isVisible()
    assert rendered_text(qtbot, page(window).viewer).startswith("Day 1")  # the heading is rendered, no "#"
    assert not page(window).type_box.isVisible()
    assert not page(window).tag_area.field.isVisible()
    assert [b.name for b in page(window).tag_area.bubbles()] == ["travel", "family"]
    assert page(window).dates_label.text().startswith("Created 21 Oct 2026, 09:01")


def test_edit_mode_edits_the_raw_markdown_and_leaving_it_saves(qtbot, window):
    click_row(qtbot, window, "Lisbon")
    page(window).edit_button.click()

    assert page(window).is_editing()
    assert page(window).editor.toPlainText().startswith("# Day 1")
    assert page(window).type_box.isVisible() and page(window).tag_area.field.isVisible()
    assert page(window).footer.isVisible()
    page(window).editor.appendPlainText("\n## Day 2")
    page(window).view_button.click()

    assert window._notebook.note(note_id(window, "Lisbon")).body.endswith("## Day 2")
    assert "Day 2" in rendered_text(qtbot, page(window).viewer)


def test_back_saves_and_returns_to_the_table(qtbot, window):
    click_row(qtbot, window, "Groceries")
    page(window).edit_button.click()
    page(window).title_edit.setText("Groceries for Sunday")

    page(window).back_button.click()

    assert view(window).is_showing_table()
    assert "Groceries for Sunday" in titles(window)


def test_switching_to_tasks_saves_the_note_being_edited(qtbot, window):
    click_row(qtbot, window, "Groceries")
    page(window).edit_button.click()
    page(window).editor.setPlainText("- eggs")

    window.show_tasks()

    assert window._notebook.note(note_id(window, "Groceries")).body == "- eggs"
    window.show_notebook()
    assert view(window).is_showing_table()


def test_edit_mode_saves_every_five_minutes(qtbot, window):
    click_row(qtbot, window, "Groceries")
    page(window).edit_button.click()

    assert page(window).autosave_timer.isActive()
    assert page(window).autosave_timer.interval() == AUTOSAVE_MS == 5 * 60 * 1000
    page(window).editor.setPlainText("- apples")
    page(window).autosave_timer.timeout.emit()

    assert window._notebook.note(note_id(window, "Groceries")).body == "- apples"
    assert page(window).is_editing()
    page(window).view_button.click()
    assert not page(window).autosave_timer.isActive()


def test_quitting_saves_the_note_being_edited(qtbot, window):
    click_row(qtbot, window, "Groceries")
    page(window).edit_button.click()
    page(window).editor.setPlainText("- cheese")

    window.close()

    assert window._notebook.note(note_id(window, "Groceries")).body == "- cheese"


def test_the_info_button_opens_a_markdown_cheat_sheet_that_any_key_closes(qtbot, window):
    click_row(qtbot, window, "Groceries")
    page(window).edit_button.click()

    page(window).info_button.click()
    sheet = page(window).cheat_sheet
    assert sheet.isVisible()
    text = sheet.findChild(type(page(window).dates_label)).text()
    assert "**bold**" in text
    assert "```mermaid" in text and "A diagram" in text  # how to write one, closing ``` included

    qtbot.keyClick(sheet, Qt.Key.Key_A)
    assert not sheet.isVisible()


# New Note


def test_new_note_opens_empty_in_edit_mode(qtbot, window):
    window.new_note_action.trigger()

    assert view(window).is_showing_note()
    assert page(window).is_editing()
    assert page(window).title_edit.text() == "" and page(window).editor.toPlainText() == ""


def test_an_empty_new_note_is_not_kept(qtbot, window):
    window.new_note_action.trigger()
    page(window).back_button.click()

    assert len(titles(window)) == 3


def test_a_new_note_with_only_a_body_becomes_a_daily_note_tagged_daily(qtbot, window):
    window.new_note_action.trigger()
    page(window).editor.setPlainText("Ran 5 km")
    page(window).back_button.click()

    new = window._notebook.notes()[0]
    assert new.title.startswith("Daily note ")
    assert new.tags == ("daily",)
    assert new.opened_at is not None
    assert view(window).is_highlighted(new.id)


def test_a_new_note_with_a_title_is_kept_once_it_leaves_edit_mode(qtbot, window):
    window.new_note_action.trigger()
    page(window).title_edit.setText("Ideas")
    page(window).view_button.click()

    assert page(window).note_id() is not None
    assert window._notebook.note(page(window).note_id()).title == "Ideas"


# Tags


def test_tags_are_added_in_edit_mode_from_suggestions_of_tasks_and_notes(qtbot, window):
    click_row(qtbot, window, "Groceries")
    page(window).edit_button.click()
    field = page(window).tag_area.field

    qtbot.keyClicks(field, "wrk")  # fuzzy: w, r, k in order
    assert page(window).tag_area.suggestions() == ["work"]  # a Task's Tag
    qtbot.keyClick(field, Qt.Key.Key_Return)
    QApplication.processEvents()

    assert page(window).tag_area.tags() == ("home", "work")
    assert field.text() == ""


def test_a_new_tag_can_be_typed_and_a_bad_one_is_refused(qtbot, window):
    click_row(qtbot, window, "Groceries")
    page(window).edit_button.click()
    area = page(window).tag_area

    assert area.add_tag("#Weekly")
    assert not area.add_tag("two words")
    assert area.field.property("invalid")

    area.remove_tag("home")
    page(window).view_button.click()
    assert window._notebook.note(note_id(window, "Groceries")).tags == ("Weekly",)


def test_a_hash_in_the_body_is_not_a_note_tag(qtbot, window):
    window.new_note_action.trigger()
    page(window).title_edit.setText("Hash")
    page(window).editor.setPlainText("#idea in the text")
    page(window).back_button.click()

    assert window._notebook.notes()[0].tags == ()


def test_the_sidebar_lists_every_tag_counted_for_the_view_on_screen(window):
    on_notebook = {b.tag: b.count for b in window.sidebar.tag_bubbles()}
    window.show_tasks()
    on_board = {b.tag: b.count for b in window.sidebar.tag_bubbles()}

    assert on_notebook == {"family": 1, "finance": 1, "home": 1, "travel": 1, "work": 0}
    assert on_board == {"family": 0, "finance": 0, "home": 0, "travel": 1, "work": 1}


def test_the_tag_filter_is_shared_by_both_views(qtbot, window):
    window.toggle_tag("travel")

    assert titles(window) == ["Lisbon"]
    window.show_tasks()
    QApplication.processEvents()
    assert [c.task.title for c in window.board_view.cards() if c.isVisible()] == ["Plan the trip"]
    window.toggle_tag("work")
    window.show_notebook()
    assert titles(window) == ["Lisbon"]
    assert window._tag_filter == {"travel", "work"}


def test_task_tags_are_suggested_from_notes_too(window):
    assert window.suggest_tags("fam") == ["family"]


# Secured Notes


def test_a_secured_note_asks_for_the_password_once_a_session(qtbot, window, asked):
    answers, calls = asked
    answers.extend(["wrong", "s3cret"])

    click_row(qtbot, window, "Bank")

    assert view(window).is_showing_note()
    assert page(window).editor.toPlainText() == "PIN 1234"
    assert page(window).lock_label.isVisible()
    page(window).back_button.click()
    click_row(qtbot, window, "Bank")
    assert len(calls) == 1


def test_cancelling_the_password_stays_in_the_table(qtbot, window, asked):
    answers, _ = asked
    answers.append(None)

    click_row(qtbot, window, "Bank")

    assert view(window).is_showing_table()
    assert window._notebook.note(note_id(window, "Bank")).opened_at is None


def test_securing_a_note_the_first_time_creates_the_password(qtbot, board, tmp_path, monkeypatch):
    vault = MemoryVault()
    notebook = Notebook(MarkdownNoteStore(tmp_path))
    notebook.create("Diary", "Dear diary")
    window = MainWindow(board, notebook=notebook, password=NotebookPassword(vault))
    qtbot.addWidget(window)
    window.show_notebook()
    monkeypatch.setattr(password_dialogs, "create_password", lambda parent: "fresh")
    click_row(qtbot, window, "Diary")
    page(window).edit_button.click()

    page(window).type_box.setCurrentIndex(1)
    page(window).type_box.activated.emit(1)
    page(window).view_button.click()

    assert vault.get() == "fresh"
    note = notebook.notes()[0]
    assert note.secured and "Dear diary" not in note.body
    assert notebook.read_body(note.id, "fresh") == "Dear diary"


def test_cancelling_the_new_password_keeps_the_note_open(qtbot, board, monkeypatch):
    notebook = Notebook()
    notebook.create("Diary", "Dear diary")
    window = MainWindow(board, notebook=notebook)
    qtbot.addWidget(window)
    window.show_notebook()
    monkeypatch.setattr(password_dialogs, "create_password", lambda parent: None)
    click_row(qtbot, window, "Diary")
    page(window).edit_button.click()

    page(window).type_box.setCurrentIndex(1)
    page(window).type_box.activated.emit(1)

    assert page(window).note_type() == NoteType.OPEN


def test_a_secured_note_can_be_made_open_again(qtbot, window, asked):
    answers, _ = asked
    answers.append("s3cret")
    click_row(qtbot, window, "Bank")
    page(window).edit_button.click()

    page(window).type_box.setCurrentIndex(0)
    page(window).type_box.activated.emit(0)
    page(window).view_button.click()

    assert window._notebook.note(note_id(window, "Bank")).body == "PIN 1234"


# Deleting


def test_deleting_an_open_note_asks_and_keeps_its_file(qtbot, window, monkeypatch, tmp_path):
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Yes)
    groceries = note_id(window, "Groceries")

    assert view(window).note_menu(groceries).actions()[0].text() == "Delete Note"
    view(window).note_menu(groceries).actions()[0].trigger()

    assert "Groceries" not in titles(window)
    assert (tmp_path / "notes" / f"{groceries}.md-deleted").exists()
    assert "home" not in {b.tag for b in window.sidebar.tag_bubbles()}


def test_saying_no_keeps_the_note(window, monkeypatch):
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.No)

    assert not view(window).delete_note(note_id(window, "Groceries"))
    assert "Groceries" in titles(window)


def test_deleting_a_secured_note_needs_the_password_and_removes_its_file(qtbot, window, asked, tmp_path):
    answers, calls = asked
    bank = note_id(window, "Bank")
    answers.append(None)
    assert not view(window).delete_note(bank)

    answers.append("s3cret")
    assert view(window).delete_note(bank)

    assert calls == ["Delete Secured Note", "Delete Secured Note"]
    assert not list((tmp_path / "notes").glob(f"{bank}*"))


def test_the_trash_on_show_note_deletes_it_and_goes_back(qtbot, window, monkeypatch):
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Yes)
    click_row(qtbot, window, "Lisbon")

    page(window).delete_button.click()

    assert view(window).is_showing_table()
    assert "Lisbon" not in titles(window)


# Importing


def test_imported_files_become_notes_and_refused_ones_are_listed(qtbot, window, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: shown.append(text))
    (tmp_path / "Trip.md").write_text("# Porto", encoding="utf-8")
    (tmp_path / "list.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (tmp_path / "old.doc").write_bytes(b"\0")

    made = view(window).import_paths([tmp_path / "Trip.md", tmp_path / "list.csv", tmp_path / "old.doc"])

    assert len(made) == 2
    trip = window._notebook.note(made[0])
    assert (trip.title, trip.body, trip.note_type, trip.tags) == ("Trip", "# Porto", NoteType.OPEN, ())
    assert window._notebook.note(made[1]).body.startswith("| a | b |")
    assert view(window).is_highlighted(made[1])
    assert len(shown) == 1 and "old.doc" in shown[0]


# Settings: the Notebook password


def test_the_password_can_be_changed_in_settings_and_every_secured_note_follows(window, vault, monkeypatch):
    monkeypatch.setattr(password_dialogs, "change_password", lambda parent, is_current: ("s3cret", "n3w"))

    assert window.change_password()

    assert vault.get() == "n3w"
    assert window._notebook.read_body(note_id(window, "Bank"), "n3w") == "PIN 1234"


def test_change_password_is_off_until_there_is_a_password(qtbot):
    from unlimilist.settings import Settings
    from unlimilist.ui.settings_dialog import SettingsDialog

    without = SettingsDialog(Settings(), has_password=False)
    with_one = SettingsDialog(Settings(), has_password=True)
    qtbot.addWidget(without)
    qtbot.addWidget(with_one)

    assert not without.change_password_button.isEnabled()
    assert with_one.change_password_button.isEnabled()


# Importing into the Note being edited


@pytest.fixture
def files(tmp_path):
    (tmp_path / "one.md").write_text("# One\n\nfirst file", encoding="utf-8")
    (tmp_path / "two.md").write_text("second file", encoding="utf-8")
    return tmp_path


def pick(monkeypatch, *paths):
    """The file dialog answers with these files."""
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *args: ([str(p) for p in paths], ""))


def edit(qtbot, window, title):
    click_row(qtbot, window, title)
    page(window).edit_button.click()


def test_importing_while_editing_adds_to_the_body_at_the_cursor_and_stays_in_edit_mode(
    qtbot, window, files, monkeypatch
):
    edit(qtbot, window, "Groceries")  # "- milk\n- bread"
    editor = page(window).editor
    window.activateWindow()
    editor.setFocus()
    qtbot.waitUntil(editor.hasFocus)
    cursor = editor.textCursor()
    cursor.setPosition(len("- milk\n"))  # the start of "- bread"
    editor.setTextCursor(cursor)
    pick(monkeypatch, files / "one.md")

    # A real click: the toolbar button must not take the focus from the editor.
    qtbot.mouseClick(window.toolbar.widgetForAction(window.import_action), Qt.MouseButton.LeftButton)

    assert view(window).is_showing_note() and page(window).is_editing()
    assert editor.toPlainText() == "- milk\n\n# One\n\nfirst file\n\n- bread"  # a blank line on each side
    assert len(titles(window)) == 3  # no new Note


def test_importing_again_and_again_keeps_adding_to_the_same_note(qtbot, window, files, monkeypatch):
    edit(qtbot, window, "Groceries")
    page(window).title_edit.setFocus()  # the Body editor is not focused: the text goes at the end

    pick(monkeypatch, files / "one.md")
    window.import_action.trigger()
    pick(monkeypatch, files / "two.md")
    window.import_action.trigger()

    assert page(window).editor.toPlainText() == "- milk\n- bread\n\n# One\n\nfirst file\n\nsecond file"
    assert page(window).is_editing()
    page(window).back_button.click()
    assert len(titles(window)) == 3
    assert window._notebook.note(note_id(window, "Groceries")).body.endswith("second file")


def test_several_files_picked_at_once_are_added_in_order(qtbot, window, files, monkeypatch):
    edit(qtbot, window, "Groceries")
    page(window).title_edit.setFocus()
    pick(monkeypatch, files / "one.md", files / "two.md")

    window.import_action.trigger()

    assert page(window).editor.toPlainText().endswith("# One\n\nfirst file\n\nsecond file")


def test_importing_in_view_mode_switches_to_edit_and_adds_at_the_end(qtbot, window, files, monkeypatch):
    click_row(qtbot, window, "Groceries")
    pick(monkeypatch, files / "two.md")

    window.import_action.trigger()

    assert page(window).is_editing()
    assert page(window).editor.toPlainText() == "- milk\n- bread\n\nsecond file"


def test_importing_into_an_empty_new_note_adds_just_the_text(qtbot, window, files, monkeypatch):
    window.new_note_action.trigger()
    pick(monkeypatch, files / "two.md")

    window.import_action.trigger()

    assert page(window).editor.toPlainText() == "second file"


def test_importing_from_the_table_still_makes_one_note_per_file(qtbot, window, files, monkeypatch):
    pick(monkeypatch, files / "one.md", files / "two.md")

    window.import_action.trigger()

    assert view(window).is_showing_table()
    assert len(titles(window)) == 5


# How the rows look: flat raised rows, bold Titles


def row_pixels(window, row, table=None):
    """The colours down a row of the table, top to bottom, as drawn: at the far end of the wide Title cell, clear
    of any text."""
    table = table or view(window).table
    QApplication.processEvents()
    image = table.viewport().grab().toImage()
    ratio = round(image.devicePixelRatio())  # 2 on a Retina screen: the image has two pixels per point
    rect = table.visualItemRect(table.item(row, TITLE))
    x = (rect.right() - 3) * ratio
    return [image.pixelColor(x, y * ratio).name() for y in range(rect.top(), rect.bottom() + 1)]


def test_every_title_is_bold_and_the_other_columns_are_regular(window):
    table = view(window).table

    for row in range(table.rowCount()):
        assert table.item(row, TITLE).font().bold()
        assert not table.item(row, CREATED).font().bold()


def test_rows_are_46_px_and_drawn_raised_flat_light_top_edge_darker_bottom_edge(window):
    from unlimilist.ui.note_rows import BOTTOM_EDGE, FILL, TOP_EDGE

    table = view(window).table
    assert table.rowHeight(0) == 46

    pixels = row_pixels(window, 1)

    assert pixels[0] == TOP_EDGE.name()
    assert pixels[len(pixels) // 2] == FILL.name()
    assert BOTTOM_EDGE.name() in pixels[-3:]
    assert len(set(pixels[3:-4])) == 1  # one flat colour between the edges: no gradient


def test_the_row_under_the_mouse_is_tinted_and_its_shade_deepens(qtbot, window):
    from unlimilist.ui.note_rows import FILL, HOVER_FILL

    table = view(window).table
    before = row_pixels(window, 1)
    rect = table.visualItemRect(table.item(1, CREATED))

    qtbot.mouseMove(table.viewport(), rect.center())
    qtbot.waitUntil(lambda: row_pixels(window, 1)[len(before) // 2] == HOVER_FILL.name())

    after = row_pixels(window, 1)
    assert after[len(after) // 2] != FILL.name()
    assert after[-2:] != before[-2:]  # a deeper shade
    assert row_pixels(window, 0)[len(before) // 2] == FILL.name()  # the others stay as they were


# Esc on a shown Note: back to the list, the Note left selected


def test_esc_on_a_note_goes_back_to_the_list_with_that_note_selected(qtbot, window):
    from unlimilist.ui.note_rows import SELECTED_ACCENT

    click_row(qtbot, window, "Groceries")

    qtbot.keyClick(page(window).viewer, Qt.Key.Key_Escape)

    assert view(window).is_showing_table()
    groceries = note_id(window, "Groceries")
    assert view(window).selected_id() == groceries
    table = view(window).table
    row = view(window).shown_ids().index(groceries)
    QApplication.processEvents()
    image = table.viewport().grab().toImage()
    ratio = round(image.devicePixelRatio())
    rect = table.visualItemRect(table.item(row, TITLE))
    assert image.pixelColor((rect.left() + 1) * ratio, rect.center().y() * ratio).name() == SELECTED_ACCENT.name()


def test_esc_in_edit_mode_saves_and_goes_back(qtbot, window):
    click_row(qtbot, window, "Groceries")
    page(window).edit_button.click()
    page(window).editor.setPlainText("- figs")

    qtbot.keyClick(page(window).editor, Qt.Key.Key_Escape)

    assert view(window).is_showing_table()
    assert window._notebook.note(note_id(window, "Groceries")).body == "- figs"


def test_esc_with_the_find_bar_open_only_closes_the_bar(qtbot, window):
    click_row(qtbot, window, "Lisbon")
    window.find()

    qtbot.keyClick(page(window).find_bar.field, Qt.Key.Key_Escape)

    assert view(window).is_showing_note() and not page(window).is_finding()
    qtbot.keyClick(page(window).viewer, Qt.Key.Key_Escape)
    assert view(window).is_showing_table()


def test_going_back_keeps_the_search_and_the_sort(qtbot, window):
    view(window).sort_by(TITLE)
    view(window).search_field.setText("milk")
    view(window).apply_search("milk")
    click_row(qtbot, window, "Groceries")

    qtbot.keyClick(page(window).viewer, Qt.Key.Key_Escape)

    assert view(window).is_searching() and titles(window) == ["Groceries"]
    assert view(window).table.horizontalHeader().sortIndicatorSection() == TITLE


def test_the_back_button_selects_the_note_too(qtbot, window):
    click_row(qtbot, window, "Lisbon")
    page(window).back_button.click()

    assert view(window).selected_id() == note_id(window, "Lisbon")


# Show Note lies over the sidebar's Tags; the Tasks and Notebook items stay


def test_a_shown_note_covers_the_sidebar_tags_but_not_the_view_items(qtbot, window):
    click_row(qtbot, window, "Lisbon")
    QApplication.processEvents()
    central = window.centralWidget()
    sidebar = window.sidebar
    views = sidebar.views.geometry()

    note = window.note_page
    assert note.isVisible() and note.geometry() == central.rect()
    assert not note.mask().contains(views.center())  # the view items stay uncovered
    tags_point = sidebar.mapTo(central, sidebar.rect().center())
    assert note.mask().contains(tags_point)  # the Tags are covered
    body = note.body_box
    assert body.mapTo(central, body.rect().topLeft()).x() < sidebar.width()  # the Body reaches under the sidebar
    assert note.header.mapTo(central, note.title_edit.pos()).x() >= sidebar.width()  # the header lines start right
    assert body.mapTo(central, body.rect().topLeft()).y() >= views.bottom()


def test_the_view_items_still_work_while_a_note_is_shown(qtbot, window):
    click_row(qtbot, window, "Groceries")
    page(window).edit_button.click()
    page(window).editor.setPlainText("- dates")
    views = window.sidebar.views

    qtbot.mouseClick(views.viewport(), Qt.MouseButton.LeftButton, pos=views.visualItemRect(views.item(0)).center())

    assert window.current_view() == "tasks"
    assert not window.note_page.isVisible()
    assert window._notebook.note(note_id(window, "Groceries")).body == "- dates"


def test_going_back_uncovers_the_tags(qtbot, window):
    click_row(qtbot, window, "Lisbon")
    page(window).back_button.click()

    assert not window.note_page.isVisible()


# Mermaid diagrams in View mode


def svg_count(qtbot, viewer) -> int:
    qtbot.waitUntil(viewer.is_rendered, timeout=10000)
    answers = []
    viewer.page().runJavaScript("document.querySelectorAll('.mermaid-block svg').length", 0, answers.append)
    qtbot.waitUntil(lambda: bool(answers), timeout=10000)
    return answers[0]


def test_a_mermaid_block_is_drawn_as_a_diagram_in_view_mode(qtbot, window):
    lisbon = note_id(window, "Lisbon")
    window._notebook.save(lisbon, "Lisbon", "Plan:\n\n```mermaid\ngraph LR\n  Flight --> Hotel\n```", (), NoteType.OPEN)

    view(window).open_note(lisbon)

    assert svg_count(qtbot, page(window).viewer) == 1
    assert "Flight" in rendered_text(qtbot, page(window).viewer)


def test_a_broken_diagram_shows_its_code_under_an_error(qtbot, window):
    lisbon = note_id(window, "Lisbon")
    window._notebook.save(lisbon, "Lisbon", "```mermaid\nthis is not a diagram\n```", (), NoteType.OPEN)

    view(window).open_note(lisbon)

    text = rendered_text(qtbot, page(window).viewer)
    assert "Diagram error" in text and "this is not a diagram" in text
    assert svg_count(qtbot, page(window).viewer) == 0


def test_a_clicked_link_opens_in_the_browser_not_in_the_app(qtbot, window, monkeypatch):
    from PySide6.QtCore import QUrl
    from PySide6.QtWebEngineCore import QWebEnginePage

    from unlimilist.ui import note_viewer

    opened = []
    monkeypatch.setattr(note_viewer.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    click_row(qtbot, window, "Lisbon")
    viewer_page = page(window).viewer.page()

    allowed = viewer_page.acceptNavigationRequest(
        QUrl("https://example.com"), QWebEnginePage.NavigationType.NavigationTypeLinkClicked, True
    )

    assert not allowed and opened == ["https://example.com"]
