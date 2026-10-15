from datetime import date, datetime, timedelta

import pytest
from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFocusEvent, QTextCursor
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox, QWidget

from unlimilist.board import Board
from unlimilist.domain import Activity, LaneKind, Stage
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


def test_a_new_task_starts_as_a_general_task_and_another_activity_can_be_picked(qtbot, board):
    dialog = TaskDialog(board)
    qtbot.addWidget(dialog)
    assert dialog.activity_buttons[Activity.GENERAL_TASK].isChecked()

    dialog.title_edit.setText("Call the bank")
    dialog.activity_buttons[Activity.PHONE_CALL].click()
    dialog.save_button.click()

    assert board.lane(Stage.INBOX, LaneKind.SOMEDAY)[0].activity == Activity.PHONE_CALL


def test_the_activity_picker_lists_ask_after_general_task_and_calls_develop_code_develop(qtbot, board):
    dialog = TaskDialog(board)
    qtbot.addWidget(dialog)

    assert [button.text() for button in dialog.activity_buttons.values()] == [
        "General Task",
        "Ask",
        "Phone call",
        "Meeting",
        "Develop",
        "Milestone",
    ]
    assert [b.x() for b in dialog.activity_buttons.values()] == sorted(b.x() for b in dialog.activity_buttons.values())


def test_an_ask_card_shows_the_ask_badge(window, board):
    board.add_task("Ask Dana about the invoice", activity=Activity.ASK)
    window.board_view.refresh()

    card = column_cards(window, Stage.INBOX)[0]

    assert card.activity_badge.property("activity") == "ask"
    assert card.activity_badge.toolTip() == "Ask"
    assert not card.activity_badge.pixmap().isNull()


def test_editing_shows_the_current_activity(qtbot, board):
    task = board.add_task("Standup", activity=Activity.MEETING)

    dialog = TaskDialog(board, task)
    qtbot.addWidget(dialog)

    checked = [a for a, button in dialog.activity_buttons.items() if button.isChecked()]
    assert checked == [Activity.MEETING]


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


def give_focus(widget):
    """Deliver the focus-in a click would; the offscreen test platform never activates windows."""
    QApplication.sendEvent(widget, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.MouseFocusReason))


def test_the_focused_editor_takes_the_room_and_keeps_it_until_the_other_is_focused(qtbot, board):
    task = board.add_task("T", details="Notes", usable_data="Link")
    dialog = TaskDialog(board, task)
    qtbot.addWidget(dialog)
    dialog.show()

    give_focus(dialog.usable_data_editor.text_edit)
    details_height, usable_height = editor_heights(dialog)
    assert usable_height > 2.5 * details_height

    give_focus(dialog.title_edit)
    details_height, usable_height = editor_heights(dialog)
    assert usable_height > 2.5 * details_height

    give_focus(dialog.details_editor.text_edit)
    details_height, usable_height = editor_heights(dialog)
    assert details_height > 2.5 * usable_height


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
    title = window.app_title
    assert (title.name(), title.version()) == ("UnlimiList", "1.9")
    assert title.accessibleName() == "UnlimiList 1.9"
    assert window.windowTitle() == "UnlimiList 1.9"


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


def test_card_shows_its_activity_badge_before_the_status_circle(window, board):
    board.add_task("Call the bank", activity=Activity.PHONE_CALL)
    window.board_view.refresh()
    QApplication.processEvents()

    card = column_cards(window, Stage.INBOX)[0]
    badge_x = card.activity_badge.mapTo(card, QPoint(0, 0)).x()
    circle_x = card.status_icon.mapTo(card, QPoint(0, 0)).x()

    assert card.activity_badge.isVisible()
    assert card.activity_badge.property("activity") == "phone-call"
    assert badge_x < circle_x


def test_the_activity_badge_is_20pt_in_the_free_strip_and_nothing_else_moves(window, board):
    board.add_task("Call the bank", activity=Activity.PHONE_CALL)
    board.add_task("Book the venue", activity=Activity.MEETING, deadline=date(2026, 10, 30))
    window.board_view.refresh()
    QApplication.processEvents()

    for card in column_cards(window, Stage.INBOX):
        badge = card.activity_badge.geometry()
        circle = card.status_icon.geometry()
        assert (badge.width(), badge.height()) == (20, 20)
        assert badge.left() >= 5 and badge.right() < circle.left()  # between the urgency stripe and the circle
        assert badge.center().y() == circle.center().y()  # level with the first title line
        # Where everything else sat with the 14 pt badge.
        assert (circle.x(), card.title_label.x()) == (28, 46)
        # The card is exactly as tall as its text: the bigger badge adds nothing.
        margins = card.layout().contentsMargins()
        text = card.title_label.height() + (card.meta_label.height() + 2 if card.meta_label.isVisible() else 0)
        assert card.height() == margins.top() + text + margins.bottom()
    dated = column_cards(window, Stage.INBOX)[0]
    assert dated.meta_label.x() == 28


def test_done_cards_have_no_activity_badge(window, board):
    task = board.add_task("Call the bank", activity=Activity.PHONE_CALL)
    board.move_task(task.id, Stage.DONE)
    window.board_view.refresh()

    card = column_cards(window, Stage.DONE)[0]

    assert card.activity_badge.isHidden()


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


def test_card_shows_its_first_tag_in_the_corner_with_how_many_more(window, board):
    board.add_task("One", details="Call #client-x")
    board.add_task("Three", details="#home, #car and #Home again, then #bank")
    board.add_task("None", usable_data="https://example.com")
    window.board_view.refresh()

    chips = {c.task.title: (None if c.tag_chip.isHidden() else c.tag_chip.text()) for c in column_cards(window, Stage.INBOX)}

    assert chips == {"One": "#client-x", "Three": "#home +2", "None": None}


def test_done_cards_show_their_tag_too(window, board):
    a = board.add_task("A", details="#work")
    board.move_task(a.id, Stage.DONE)
    window.board_view.refresh()

    assert column_cards(window, Stage.DONE)[0].tag_chip.text() == "#work"


def test_cards_no_longer_flag_usable_data(window, board):
    board.add_task("A", usable_data="https://example.com")
    window.board_view.refresh()

    card = column_cards(window, Stage.INBOX)[0]

    assert "📎" not in [label.text() for label in card.findChildren(QLabel)]


def bubbles(window):
    return {b.tag: (b.count, b.is_selected()) for b in window.sidebar.tag_bubbles()}


def click_bubble(qtbot, window, tag):
    bubble = next(b for b in window.sidebar.tag_bubbles() if b.tag == tag)
    qtbot.mouseClick(bubble, Qt.MouseButton.LeftButton)


def lane_headers(window, stage):
    return window.board_view.column_widget(stage).lane_headers()


@pytest.fixture
def tagged(board):
    board.add_task("Plan", details="#home")
    board.add_task("Code", details="#work #home")
    board.add_task("Read")
    board.add_task("Demo", details="#client-x", deadline=date(2026, 11, 1))
    board.add_task("Book", deadline=date(2026, 11, 2))
    done = board.add_task("Retro", details="#work")
    board.move_task(done.id, Stage.DONE)
    return board


def test_sidebar_lists_every_tag_a_to_z_with_its_count(window, tagged):
    window.refresh()

    assert [b.tag for b in window.sidebar.tag_bubbles()] == ["client-x", "home", "work"]
    assert bubbles(window) == {"client-x": (1, False), "home": (2, False), "work": (2, False)}
    assert not window.sidebar.clear_button.isEnabled()


def test_selecting_tags_shows_tasks_with_any_of_them(qtbot, window, tagged):
    window.refresh()

    click_bubble(qtbot, window, "work")
    click_bubble(qtbot, window, "client-x")

    assert card_titles(window, Stage.INBOX) == ["Demo", "2. Code"]  # real Priority kept
    assert card_titles(window, Stage.DONE) == ["Retro"]
    assert lane_headers(window, Stage.INBOX) == ("SOMEDAY  ·  1 of 3", "TIME-LIMITED  ·  1 of 2")
    assert lane_headers(window, Stage.DONE) == ("COMPLETED  ·  1 of 1", None)
    assert window.sidebar.clear_button.isEnabled()
    assert window.sidebar.clear_button.text() == "✕ Clear (2)"


def test_clicking_a_selected_tag_unselects_it(qtbot, window, tagged):
    window.refresh()

    click_bubble(qtbot, window, "home")
    click_bubble(qtbot, window, "home")

    assert len(card_titles(window, Stage.INBOX)) == 5
    assert lane_headers(window, Stage.INBOX) == ("SOMEDAY  ·  3", "TIME-LIMITED  ·  2")


@pytest.mark.parametrize("how", ["clear", "everything"])
def test_clear_and_everything_unselect_all_tags(qtbot, window, tagged, how):
    window.refresh()
    click_bubble(qtbot, window, "home")

    if how == "clear":
        window.sidebar.clear_button.click()
    else:
        views = window.sidebar.views
        qtbot.mouseClick(views.viewport(), Qt.MouseButton.LeftButton, pos=views.visualItemRect(views.item(0)).center())

    assert all(not selected for _, selected in bubbles(window).values())
    assert len(card_titles(window, Stage.INBOX)) == 5
    assert not window.sidebar.clear_button.isEnabled()


def test_a_filtered_card_keeps_the_shade_it_has_on_the_full_board(qtbot, window, tagged):
    window.refresh()
    QApplication.processEvents()
    before = {c.task.title: c.fill() for c in column_cards(window, Stage.INBOX)}

    click_bubble(qtbot, window, "client-x")
    click_bubble(qtbot, window, "home")

    after = {c.task.title: c.fill() for c in column_cards(window, Stage.INBOX)}
    assert after == {title: before[title] for title in after}
    assert set(after) == {"Demo", "Plan", "Code"}


def test_quick_adding_a_task_clears_the_tag_filter(qtbot, window, tagged):
    window.refresh()
    click_bubble(qtbot, window, "home")

    qtbot.keyClicks(window.board_view.quick_add, "Buy milk")
    qtbot.keyClick(window.board_view.quick_add, Qt.Key.Key_Return)

    assert "4. Buy milk" in card_titles(window, Stage.INBOX)
    assert not window.sidebar.clear_button.isEnabled()


def test_creating_a_task_in_the_dialog_clears_the_tag_filter_even_if_it_matches(qtbot, window, tagged, monkeypatch):
    window.refresh()
    click_bubble(qtbot, window, "home")

    def create(dialog):
        dialog.title_edit.setText("Water plants")
        dialog.details_editor.set_markdown("#home")
        dialog.save_button.click()
        return dialog.result()

    monkeypatch.setattr(TaskDialog, "exec", create)
    window.new_task()

    assert len(card_titles(window, Stage.INBOX)) == 6
    assert not window.sidebar.clear_button.isEnabled()


def test_a_task_edited_out_of_the_filter_clears_the_filter_and_is_highlighted(qtbot, window, tagged, monkeypatch):
    window.refresh()
    click_bubble(qtbot, window, "home")
    code = next(c.task for c in column_cards(window, Stage.INBOX) if c.task.title == "Code")

    def drop_home(dialog):
        dialog.details_editor.set_markdown("#work")
        dialog.save_button.click()
        return dialog.result()

    monkeypatch.setattr(TaskDialog, "exec", drop_home)
    window.open_task(code.id)

    assert not window.sidebar.clear_button.isEnabled()
    assert [c.task.title for c in column_cards(window, Stage.INBOX) if c.is_highlighted()] == ["Code"]


def test_a_selected_tag_that_no_task_has_any_more_drops_out_of_the_filter(qtbot, window, tagged, monkeypatch):
    window.refresh()
    click_bubble(qtbot, window, "client-x")
    demo = column_cards(window, Stage.INBOX)[0].task

    def drop_tag(dialog):
        dialog.details_editor.set_markdown("No tags now")
        dialog.save_button.click()
        return dialog.result()

    monkeypatch.setattr(TaskDialog, "exec", drop_tag)
    window.open_task(demo.id)

    assert "client-x" not in bubbles(window)
    assert not window.sidebar.clear_button.isEnabled()
    assert len(card_titles(window, Stage.INBOX)) == 5


def test_while_filtered_a_drop_in_its_own_stage_is_refused_with_a_hint(qtbot, window, board):
    board.add_task("A", details="#x")
    board.add_task("B")
    c = board.add_task("C", details="#x")
    window.refresh()
    click_bubble(qtbot, window, "x")
    column = window.board_view.column_widget(Stage.INBOX)
    mime = encode_drag(board.task(c.id))

    column.dragEnterEvent(
        QDragEnterEvent(QPointF(20, 60), Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    )
    hint = column.drop_hint()
    drop_on_column(window, board.task(c.id), Stage.INBOX, at_top=True)

    assert hint == "Clear the Tag filter to reorder"
    assert [t.title for t in board.lane(Stage.INBOX, LaneKind.SOMEDAY)] == ["A", "B", "C"]


def test_while_filtered_a_someday_task_dropped_in_another_stage_lands_at_the_bottom(qtbot, window, board):
    a = board.add_task("A", details="#x")
    for title in ("P1", "P2"):
        board.move_task(board.add_task(title).id, Stage.IN_PROCESS)
    window.refresh()
    click_bubble(qtbot, window, "x")

    drop_on_column(window, board.task(a.id), Stage.IN_PROCESS, at_top=True)

    assert [(t.title, t.priority) for t in board.lane(Stage.IN_PROCESS, LaneKind.SOMEDAY)] == [("P1", 1), ("P2", 2), ("A", 3)]


def underlined_words(editor):
    """The text the editor draws underlined, block by block (links excluded)."""
    words = []
    block = editor.text_edit.document().firstBlock()
    while block.isValid():
        for extra in block.layout().formats():
            if extra.format.fontUnderline():
                words.append(block.text()[extra.start : extra.start + extra.length])
        block = block.next()
    return words


def test_details_editor_underlines_tags_but_not_in_code_or_usable_data(qtbot, board):
    task = board.add_task("T", details="Call #client-x, not issue#12 or `#define`\n\n#home", usable_data="#bank")
    dialog = TaskDialog(board, task)
    qtbot.addWidget(dialog)

    dialog.details_editor.text_edit.moveCursor(QTextCursor.MoveOperation.End)
    qtbot.keyClicks(dialog.details_editor.text_edit, " #new")

    assert underlined_words(dialog.details_editor) == ["#client-x", "#home", "#new"]
    assert underlined_words(dialog.usable_data_editor) == []


def suggestions(editor):
    popup = editor.tag_popup
    if popup is None or popup.isHidden():
        return []
    return [popup.item(i).text() for i in range(popup.count())]


@pytest.fixture
def tag_dialog(qtbot, board):
    board.add_task("A", details="#work #weekly #network #home")
    board.add_task("B", details="#work")
    dialog = TaskDialog(board)
    qtbot.addWidget(dialog)
    return dialog


def test_typing_a_hash_and_a_letter_suggests_existing_tags(qtbot, tag_dialog):
    editor = tag_dialog.details_editor

    qtbot.keyClicks(editor.text_edit, "Call #")
    nothing_yet = suggestions(editor)
    qtbot.keyClicks(editor.text_edit, "w")

    assert nothing_yet == []
    assert suggestions(editor) == ["#work", "#weekly", "#network"]


def test_enter_inserts_the_chosen_suggestion(qtbot, tag_dialog):
    editor = tag_dialog.details_editor
    qtbot.keyClicks(editor.text_edit, "Call #wk")

    qtbot.keyClick(editor.text_edit, Qt.Key.Key_Down)
    qtbot.keyClick(editor.text_edit, Qt.Key.Key_Return)

    assert editor.text_edit.toPlainText() == "Call #network "
    assert suggestions(editor) == []


def test_tab_inserts_the_top_suggestion(qtbot, tag_dialog):
    editor = tag_dialog.details_editor
    qtbot.keyClicks(editor.text_edit, "#ho")

    qtbot.keyClick(editor.text_edit, Qt.Key.Key_Tab)

    assert editor.text_edit.toPlainText() == "#home "


@pytest.mark.parametrize("key", [Qt.Key.Key_Escape, Qt.Key.Key_Space])
def test_escape_or_a_space_closes_the_suggestions(qtbot, tag_dialog, key):
    editor = tag_dialog.details_editor
    qtbot.keyClicks(editor.text_edit, "#wo")

    qtbot.keyClick(editor.text_edit, key)

    assert suggestions(editor) == []
    assert editor.text_edit.toPlainText().startswith("#wo")


def test_new_tags_get_no_suggestions_and_usable_data_never_does(qtbot, tag_dialog):
    qtbot.keyClicks(tag_dialog.details_editor.text_edit, "#zebra")
    qtbot.keyClicks(tag_dialog.usable_data_editor.text_edit, "#wo")

    assert suggestions(tag_dialog.details_editor) == []
    assert suggestions(tag_dialog.usable_data_editor) == []


def test_redrawing_the_tags_leaves_only_the_current_bubbles_in_the_sidebar(qtbot, window, tagged):
    window.refresh()

    click_bubble(qtbot, window, "home")
    click_bubble(qtbot, window, "work")

    from unlimilist.ui.sidebar import TagBubble

    assert len(window.sidebar.findChildren(TagBubble)) == 3


def card_texts(card):
    return " ".join(label.text() for label in card.findChildren(QLabel))


def test_cards_show_no_details(window, board):
    board.add_task("Groceries", details="Oat milk and bread\n\n- [ ] eggs")
    window.board_view.refresh()

    card = column_cards(window, Stage.INBOX)[0]

    assert "Oat" not in card_texts(card) and "eggs" not in card_texts(card)
    assert card.meta_label.isHidden()  # Someday cards have no dates line


@pytest.mark.parametrize(
    ("details", "chip"),
    [
        ("#client-x #home", "#client-x +1"),  # exactly 12 characters
        ("#reading-list", "#reading-li…"),
        ("#reading-list #a #b", "#reading… +2"),
    ],
)
def test_the_tag_chip_is_cut_to_12_characters(window, board, details, chip):
    board.add_task("T", details=details)
    window.board_view.refresh()

    text = column_cards(window, Stage.INBOX)[0].tag_chip.text()

    assert (text, len(text)) == (chip, 12)


LONG_TITLE = " ".join(["Prepare the quarterly report for the board meeting with every number and chart"] * 5)


@pytest.mark.parametrize(("deadline", "title_lines"), [(None, 4), (date(2026, 11, 1), 3)])
def test_a_long_title_wraps_over_every_line_of_the_card(window, board, deadline, title_lines):
    board.add_task(LONG_TITLE, details="#work", deadline=deadline)
    window.board_view.refresh()

    lines = column_cards(window, Stage.INBOX)[0].title_label.text().split("\n")

    assert len(lines) == title_lines
    assert lines[-1].endswith("…")


def test_the_tag_chip_shares_only_the_first_title_line(window, board):
    board.add_task(LONG_TITLE, details="#work")
    board.add_task(LONG_TITLE)
    window.board_view.refresh()
    QApplication.processEvents()

    tagged, plain = column_cards(window, Stage.INBOX)
    tagged_lines = tagged.title_label.text().split("\n")
    plain_lines = plain.title_label.text().split("\n")
    title_top = tagged.title_label.mapTo(tagged, QPoint(0, 0)).y()
    line_height = tagged.title_label.fontMetrics().height()

    assert len(tagged_lines[0]) < len(plain_lines[0])  # the first line makes room for the chip
    assert tagged.title_label.width() == plain.title_label.width()  # later lines get the card's full width
    assert title_top <= tagged.tag_chip.geometry().center().y() <= title_top + line_height  # on the first line


def test_the_suggestions_belong_to_the_dialog_window_so_they_show_above_it(qtbot, tag_dialog):
    # The Task dialog is modal, and macOS raises a modal window above free-floating ones. A window with the
    # dialog as its transient parent is kept at the dialog's level, so the suggestions stay on top of it.
    tag_dialog.show()
    qtbot.waitExposed(tag_dialog)

    qtbot.keyClicks(tag_dialog.details_editor.text_edit, "#w")

    popup = tag_dialog.details_editor.tag_popup
    assert popup.isVisible()
    assert popup.windowHandle().transientParent() is tag_dialog.windowHandle()


def red_pixels(image, rect, scale):
    left, top = int(rect.left() * scale), int(rect.top() * scale)
    right, bottom = int(rect.right() * scale), int(rect.bottom() * scale)
    return sum(is_red(image.pixelColor(x, y)) for x in range(left, right) for y in range(top, bottom))


def test_toolbar_title_rings_the_l_and_writes_the_version_in_red(window):
    title = window.app_title
    image = title.grab().toImage()
    scale = image.devicePixelRatio()
    ring = title.ring_rect()

    assert is_red(image.pixelColor(int(ring.center().x() * scale), int((ring.top() + 0.5) * scale)))  # top of the ring
    assert red_pixels(image, title.version_rect(), scale) > 0
    assert red_pixels(image, title.name_rect_before_ring(), scale) == 0  # "Unlimi" stays black


def ink_pixels(widget, scale=4):
    """Positions (in widget pixels) of the dark, non-red pixels the widget draws, rendered at `scale`."""
    from PySide6.QtGui import QPixmap

    pixmap = QPixmap(widget.size() * scale)
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(Qt.GlobalColor.white)
    widget.render(pixmap)
    image = pixmap.toImage()
    dark = []
    for x in range(image.width()):
        for y in range(image.height()):
            colour = image.pixelColor(x, y)
            if colour.lightness() < 110 and colour.red() - colour.green() < 60:
                dark.append(((x + 0.5) / scale, (y + 0.5) / scale))
    return dark


def test_toolbar_title_centres_the_l_in_its_ring_and_no_letter_touches_the_ring(window):
    title = window.app_title
    ring = title.ring_rect()
    cx, cy = ring.center().x(), ring.center().y()
    outer = ring.width() / 2
    inner = outer - title.ring_width()

    def distance(point):
        return ((point[0] - cx) ** 2 + (point[1] - cy) ** 2) ** 0.5

    ink = ink_pixels(title)
    inside = [p for p in ink if distance(p) < inner]
    touching = [p for p in ink if inner - 1 <= distance(p) <= outer + 2]

    xs, ys = [p[0] for p in inside], [p[1] for p in inside]
    assert abs((min(xs) + max(xs)) / 2 - cx) <= 0.5  # the L is centred across the ring
    assert abs((min(ys) + max(ys)) / 2 - cy) <= 0.5  # and from top to bottom
    assert touching == []  # nothing dark on the ring or within 2 px outside it


def test_drawing_cards_opens_no_stray_windows(window, board):
    # A label shown before it has a parent becomes a window of its own: slow, and it can flash on screen.
    for n in range(5):
        board.add_task(f"S{n}", details="#work")
    board.add_task("T", deadline=date(2026, 11, 1))
    done = board.add_task("D")
    board.move_task(done.id, Stage.DONE)
    created = []

    class Spy(QObject):
        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.Show and isinstance(watched, QWidget) and watched.isWindow():
                created.append(type(watched).__name__)
            return False

    spy = Spy()
    QApplication.instance().installEventFilter(spy)
    try:
        window.board_view.refresh()
    finally:
        QApplication.instance().removeEventFilter(spy)

    assert created == []
