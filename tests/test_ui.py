from datetime import date, datetime, timedelta

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QTextCursor
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


def test_task_dialog_is_900_pixels_wide(qtbot, board):
    dialog = TaskDialog(board)
    qtbot.addWidget(dialog)

    assert dialog.width() == 900


def test_new_task_dialog_has_no_delete_button(qtbot, board):
    dialog = TaskDialog(board)
    qtbot.addWidget(dialog)

    assert dialog.delete_button.isHidden()


def test_delete_is_disabled_for_a_task_in_process(qtbot, board):
    a = board.add_task("A")
    board.move_task(a.id, Stage.IN_PROCESS)

    dialog = TaskDialog(board, board.task(a.id))
    qtbot.addWidget(dialog)

    assert not dialog.delete_button.isHidden()
    assert not dialog.delete_button.isEnabled()
    assert "In Process" in dialog.delete_button.toolTip()


def test_add_subtask_goes_after_the_last_subtask_and_before_other_text(qtbot, board):
    task = board.add_task("Ship", details="- [x] Build\n\nRelease notes go here")
    dialog = TaskDialog(board, task)
    qtbot.addWidget(dialog)
    editor = dialog.details_editor

    editor.add_subtask_button.click()
    qtbot.keyClicks(editor.text_edit, "Test")
    dialog.save_button.click()

    assert board.task(task.id).details.splitlines() == ["- [x] Build", "- [ ] Test", "", "Release notes go here"]


def test_the_first_subtask_goes_before_existing_text(qtbot, board):
    task = board.add_task("Ship", details="Release notes go here")
    dialog = TaskDialog(board, task)
    qtbot.addWidget(dialog)

    dialog.details_editor.add_subtask_button.click()
    qtbot.keyClicks(dialog.details_editor.text_edit, "Build")
    dialog.save_button.click()

    assert board.task(task.id).details.splitlines() == ["- [ ] Build", "", "Release notes go here"]


def subtask_box_point(editor, row):
    """A point on the checkbox drawn left of Subtask number `row`."""
    block = editor.text_edit.document().findBlockByNumber(row)
    cursor = editor.text_edit.textCursor()
    cursor.setPosition(block.position())
    rect = editor.text_edit.cursorRect(cursor)
    return QPoint(rect.left() - 10, rect.center().y())


def test_clicking_a_subtask_box_ticks_it(qtbot, board):
    task = board.add_task("Ship", details="- [ ] Build\n- [x] Test")
    dialog = TaskDialog(board, task)
    qtbot.addWidget(dialog)
    dialog.show()
    editor = dialog.details_editor
    viewport = editor.text_edit.viewport()

    qtbot.mouseClick(viewport, Qt.MouseButton.LeftButton, pos=subtask_box_point(editor, 0))
    qtbot.mouseClick(viewport, Qt.MouseButton.LeftButton, pos=subtask_box_point(editor, 1))
    dialog.save_button.click()

    assert board.task(task.id).details.splitlines() == ["- [x] Build", "- [ ] Test"]


def test_enter_after_a_ticked_subtask_adds_an_unfinished_one(qtbot, board):
    task = board.add_task("Ship", details="- [x] Build")
    dialog = TaskDialog(board, task)
    qtbot.addWidget(dialog)
    text_edit = dialog.details_editor.text_edit
    text_edit.moveCursor(QTextCursor.MoveOperation.End)

    qtbot.keyClick(text_edit, Qt.Key.Key_Return)
    qtbot.keyClicks(text_edit, "Test")
    dialog.save_button.click()

    assert board.task(task.id).details.splitlines() == ["- [x] Build", "- [ ] Test"]


def test_backspace_on_an_empty_subtask_removes_it(qtbot, board):
    task = board.add_task("Ship", details="- [x] Build\n\nNotes")
    dialog = TaskDialog(board, task)
    qtbot.addWidget(dialog)
    editor = dialog.details_editor

    editor.add_subtask_button.click()
    qtbot.keyClick(editor.text_edit, Qt.Key.Key_Backspace)
    dialog.save_button.click()

    assert board.task(task.id).details.splitlines() == ["- [x] Build", "", "Notes"]


def test_details_editor_has_no_placeholder(qtbot, board):
    dialog = TaskDialog(board)
    qtbot.addWidget(dialog)

    assert dialog.details_editor.text_edit.placeholderText() == ""


def editor_heights(dialog):
    QApplication.processEvents()
    return dialog.details_editor.height(), dialog.usable_data_editor.height()


@pytest.mark.parametrize(
    ("details", "usable_data", "bigger"),
    [("", "", "details"), ("Notes", "", "details"), ("", "https://example.com", "usable_data"), ("Notes", "Link", "neither")],
)
def test_the_editor_with_text_gets_the_room(qtbot, board, details, usable_data, bigger):
    task = board.add_task("T", details=details, usable_data=usable_data)
    dialog = TaskDialog(board, task)
    qtbot.addWidget(dialog)
    dialog.show()

    details_height, usable_height = editor_heights(dialog)

    if bigger == "details":
        assert details_height > 2.5 * usable_height
    elif bigger == "usable_data":
        assert usable_height > 2.5 * details_height
    else:
        assert details_height == pytest.approx(usable_height, abs=4)


def test_the_split_follows_typing(qtbot, board):
    dialog = TaskDialog(board)
    qtbot.addWidget(dialog)
    dialog.show()

    qtbot.keyClicks(dialog.usable_data_editor.text_edit, "https://example.com")
    details_height, usable_height = editor_heights(dialog)

    assert usable_height > 2.5 * details_height


def test_only_details_can_add_subtasks(qtbot, board):
    dialog = TaskDialog(board)
    qtbot.addWidget(dialog)

    assert dialog.usable_data_editor.add_subtask_button is None


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


def test_window_opens_at_1500_by_950_or_the_screen_size_if_smaller(window):
    screen = window.screen().availableGeometry()
    smallest = window.minimumSizeHint()  # the test screen is tiny; the window never shrinks below its content

    assert window.width() == max(min(1500, screen.width()), smallest.width())
    assert window.height() == max(min(950, screen.height()), smallest.height())


def test_window_has_the_app_icon(window):
    assert not window.windowIcon().isNull()
    assert window.windowIcon().availableSizes()[0].width() >= 512


def test_toolbar_shows_the_app_name_with_its_version(window):
    assert window.app_title.text() == "UnlimiList"
    assert window.version_badge.text() == "1.4"
    assert window.windowTitle() == "UnlimiList 1.4"


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


def test_every_card_has_a_status_circle_before_its_title(window, board):
    board.add_task("Plain")
    board.add_task("Checklist", details="- [x] Build\n- [ ] Test")
    finished = board.add_task("Finished", details="- [x] Build")
    board.move_task(finished.id, Stage.DONE)
    window.board_view.refresh()
    QApplication.processEvents()

    fills = {c.task.title: c.status_icon.property("fill") for c in column_cards(window, Stage.INBOX)}
    done = column_cards(window, Stage.DONE)[0]

    assert fills == {"Plain": "empty", "Checklist": "two_thirds"}
    assert done.status_icon.property("fill") == "full"
    assert done.status_icon.x() < done.title_label.x()


def test_card_preview_leaves_out_subtasks(window, board):
    board.add_task("Ship", details="- [x] Build\n- [ ] Test\n\nRemember the icon")
    board.add_task("Checklist only", details="- [ ] Test")
    window.board_view.refresh()

    ship, checklist = column_cards(window, Stage.INBOX)

    assert ship.details_label.text() == "Remember the icon"
    assert checklist.details_label.isHidden()


def edge_colour(card):
    """The colour of the card's right edge, halfway down."""
    return card.grab().toImage().pixelColor(card.width() - 1, card.height() // 2)


def is_red(colour):
    return colour.red() > 180 and colour.green() < 90 and colour.blue() < 90


def test_late_cards_have_a_red_border(window, board):
    # The board's today is 12/10/2026.
    board.add_task("Overdue", deadline=date(2026, 10, 10))
    board.add_task("Start passed", due_date=date(2026, 10, 10), deadline=date(2026, 10, 30))
    board.add_task("Due soon", deadline=date(2026, 10, 13))
    started = board.add_task("Started", due_date=date(2026, 10, 10))
    board.move_task(started.id, Stage.IN_PROCESS)
    window.board_view.refresh()
    QApplication.processEvents()

    red = {c.task.title: is_red(edge_colour(c)) for s in (Stage.INBOX, Stage.IN_PROCESS) for c in column_cards(window, s)}

    assert red == {"Overdue": True, "Start passed": True, "Due soon": False, "Started": False}


def test_dropping_a_card_in_another_stage_moves_it(window, board):
    a = board.add_task("A")
    window.board_view.refresh()

    drop_on_column(window, board.task(a.id), Stage.DONE)

    assert card_titles(window, Stage.DONE) == ["A"]
    assert card_titles(window, Stage.INBOX) == []


def test_dropping_a_task_with_unfinished_subtasks_on_done_keeps_it_and_shows_a_balloon(window, board):
    a = board.add_task("Ship", details="- [x] Build\n- [ ] Test\n- [ ] Release")
    window.board_view.refresh()

    drop_on_column(window, board.task(a.id), Stage.DONE)

    assert card_titles(window, Stage.INBOX) == ["1. Ship"]
    assert card_titles(window, Stage.DONE) == []
    assert window.balloon.isVisible()
    assert window.balloon.text() == "You still have 2 unfinished subtasks"


def test_dragging_a_task_with_unfinished_subtasks_over_done_shows_a_hint(window, board):
    a = board.add_task("Ship", details="- [ ] Test")
    window.board_view.refresh()
    column = window.board_view.column_widget(Stage.DONE)
    mime = encode_drag(board.task(a.id))

    column.dragEnterEvent(
        QDragEnterEvent(QPointF(20, 60), Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    )

    assert column.drop_hint() == "1 unfinished subtask"


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
