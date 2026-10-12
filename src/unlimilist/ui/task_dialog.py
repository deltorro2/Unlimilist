"""The modal dialog that creates or edits a Task."""

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from unlimilist.board import Board
from unlimilist.domain import InvalidTask, Stage, Task
from unlimilist.ui.date_field import DateField
from unlimilist.ui.icons import icon, pixmap
from unlimilist.ui.rich_text import RichTextEditor

BOTTOM_PRIORITY = 999  # a rank past the bottom: the Board puts the Task last
_LOCKED_BY_DATES = "Unavailable while a due date or deadline is set"
_LOCKED_BY_DONE = "Not used for Done Tasks"
_NEEDS_A_DATE = "Add a Due date or Deadline to make this a Time-limited Task."
_DELETE_LOCKED = "Move the Task out of In Process to delete it"
# How Details and Usable data share the room: the editor with text gets more of it.
_SPLIT_FOR_DETAILS = (4, 1)
_SPLIT_FOR_USABLE_DATA = (1, 4)
_SPLIT_EVEN = (1, 1)

STYLESHEET = """
QDialog#taskDialog { background: #F2F2F5; }
QLabel#fieldLabel { color: #6B6F7A; font-size: 13px; font-weight: 600; }
QLabel#required { color: #D32F2F; font-size: 13px; font-weight: 600; }
QLineEdit#titleEdit {
    background: #FFFFFF; border: 1px solid #D5D7DD; border-radius: 8px;
    padding: 9px 12px; font-size: 17px; font-weight: 500; color: #1B1B1F;
}
QLineEdit#titleEdit:focus { border: 2px solid #2F7BEA; padding: 8px 11px; }

QFrame#editorBox { background: #FFFFFF; border: 1px solid #D5D7DD; border-radius: 8px; }
QWidget#editorToolbar { background: #F7F7F9; border: none; border-bottom: 1px solid #E4E5EA;
    border-top-left-radius: 8px; border-top-right-radius: 8px; }
QToolButton#editorButton { background: transparent; border: none; border-radius: 5px; padding: 4px; }
QToolButton#editorButton:hover { background: #E7E8EC; }
QFrame#toolbarSeparator { background: #D9DBE0; }
QTextEdit#editorText { background: #FFFFFF; border: none; padding: 8px 10px; font-size: 14px; color: #1B1B1F;
    border-bottom-left-radius: 8px; border-bottom-right-radius: 8px; }

QFrame#dateBox { background: #FFFFFF; border: 1px solid #D5D7DD; border-radius: 8px; }
QFrame#dateBox[state="focused"] { border: 1px solid #2F7BEA; }
QFrame#dateBox[state="invalid"] { border: 1px solid #E53935; }
QLineEdit#dateText { background: transparent; border: none; font-size: 15px; color: #1B1B1F; padding: 4px 0; }
QToolButton#dateCalendar { background: transparent; border: none; padding: 2px; }
QToolButton#dateCalendar::menu-indicator { image: none; width: 0; }
QToolButton#dateClear { background: #E6E7EB; border: none; border-radius: 13px; min-width: 26px; max-width: 26px;
    min-height: 26px; max-height: 26px; }
QToolButton#dateClear:hover { background: #D8DAE0; }

QFrame#stepper { background: #FFFFFF; border: 1px solid #D5D7DD; border-radius: 8px; }
QFrame#stepper:disabled { background: #F7F7F9; border-color: #E2E3E8; }
QToolButton#stepButton { background: transparent; border: none; min-width: 34px; min-height: 34px; }
QToolButton#stepButton:hover { background: #F0F1F4; }
QSpinBox#prioritySpin { background: transparent; border: none; font-size: 16px; color: #1B1B1F; min-width: 64px; }
QSpinBox#prioritySpin::up-button, QSpinBox#prioritySpin::down-button {
    subcontrol-origin: border; width: 0px; height: 0px; }
QFrame#stepperLine { background: #E2E3E8; }
QSpinBox#prioritySpin:disabled { color: #A9ACB4; }
QLabel#priorityNote { color: #6B6F7A; font-size: 13px; }

QLabel#errorLabel { color: #D32F2F; font-size: 13px; }
QFrame#footerLine { background: #DFE0E5; }
QWidget#footer { background: #F2F2F5; }
QPushButton#deleteButton { background: transparent; border: none; color: #D32F2F; font-size: 15px;
    font-weight: 500; padding: 6px 4px; text-align: left; }
QPushButton#deleteButton:hover { color: #B71C1C; }
QPushButton#deleteButton:disabled { color: #B8BBC3; }
QPushButton#cancelButton { background: #FFFFFF; border: 1px solid #D5D7DD; border-radius: 8px;
    padding: 8px 26px; font-size: 15px; color: #1B1B1F; }
QPushButton#cancelButton:hover { background: #F7F7F9; }
QPushButton#saveButton { background: #1F6FE5; border: none; border-radius: 8px; padding: 9px 32px;
    font-size: 15px; font-weight: 600; color: #FFFFFF; }
QPushButton#saveButton:hover { background: #185CC2; }
"""


def _label(text: str, required: bool = False) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(2, 0, 0, 0)
    layout.setSpacing(3)
    label = QLabel(text)
    label.setObjectName("fieldLabel")
    layout.addWidget(label)
    if required:
        star = QLabel("*")
        star.setObjectName("required")
        layout.addWidget(star)
    layout.addStretch(1)
    return row


class TaskDialog(QDialog):
    def __init__(self, board: Board, task: Task | None = None, parent=None, require_date: bool = False):
        """`require_date` is used when a Someday Task is dropped on the Time-limited side of a Column."""
        super().__init__(parent)
        self._board = board
        self._task = task
        self._require_date = require_date
        self.setObjectName("taskDialog")
        self.setStyleSheet(STYLESHEET)
        self.setWindowTitle("Edit Task" if task else "New Task")
        self.setModal(True)
        self.setMinimumWidth(640)
        self.resize(900, 860)

        self.title_edit = QLineEdit()
        self.title_edit.setObjectName("titleEdit")
        self.title_edit.setPlaceholderText("What needs doing?")
        self.details_editor = RichTextEditor(subtasks=True)
        self.usable_data_editor = RichTextEditor("Links, snippets, reference info…")
        self.due_date_field = DateField()
        self.deadline_field = DateField()

        dates = QGridLayout()
        dates.setHorizontalSpacing(24)
        dates.setVerticalSpacing(8)
        dates.addWidget(_label("Due date"), 0, 0)
        dates.addWidget(_label("Deadline"), 0, 1)
        dates.addWidget(self.due_date_field, 1, 0)
        dates.addWidget(self.deadline_field, 1, 1)

        content = self._content = QVBoxLayout()
        content.setContentsMargins(26, 18, 26, 12)
        content.setSpacing(8)
        content.addWidget(_label("Title", required=True))
        content.addWidget(self.title_edit)
        content.addSpacing(10)
        content.addWidget(_label("Details"))
        content.addWidget(self.details_editor, 1)
        content.addSpacing(10)
        content.addWidget(_label("Usable data"))
        content.addWidget(self.usable_data_editor, 1)
        content.addSpacing(10)
        content.addLayout(dates)
        content.addSpacing(10)
        content.addWidget(_label("Priority"))
        content.addLayout(self._build_priority())

        self.error_label = QLabel(_NEEDS_A_DATE if require_date else "")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        content.addWidget(self.error_label)

        footer_line = QFrame()
        footer_line.setObjectName("footerLine")
        footer_line.setFixedHeight(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(content, 1)
        layout.addWidget(footer_line)
        layout.addWidget(self._build_footer())

        if task:
            self.title_edit.setText(task.title)
            self.details_editor.set_markdown(task.details)
            self.usable_data_editor.set_markdown(task.usable_data)
            self.due_date_field.set_date(task.due_date)
            self.deadline_field.set_date(task.deadline)
        self.priority_spin.setValue(task.priority if task and task.priority is not None else BOTTOM_PRIORITY)
        # Until an editor is focused, the split follows the content; after that, the last focused editor leads.
        self._focused_editor: RichTextEditor | None = None
        for editor in (self.details_editor, self.usable_data_editor):
            editor.text_edit.textChanged.connect(self._update_split)
            editor.text_edit.installEventFilter(self)
        self._update_split()
        self.due_date_field.dateChanged.connect(self._update_priority_lock)
        self.deadline_field.dateChanged.connect(self._update_priority_lock)
        self._update_priority_lock()
        self.title_edit.setFocus()

    def _build_priority(self) -> QHBoxLayout:
        self.priority_spin = QSpinBox()
        self.priority_spin.setObjectName("prioritySpin")
        self.priority_spin.setRange(1, BOTTOM_PRIORITY)
        self.priority_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.priority_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.priority_spin.setToolTip(f"1 is the top of the Lane; {BOTTOM_PRIORITY} means the bottom")

        minus, plus = QToolButton(), QToolButton()
        for button, name, step in [(minus, "minus", self.priority_spin.stepDown), (plus, "plus", self.priority_spin.stepUp)]:
            button.setObjectName("stepButton")
            button.setIcon(icon(name, "#6B6F7A", 16))
            button.setIconSize(QSize(16, 16))
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(step)

        self._stepper = QFrame()
        self._stepper.setObjectName("stepper")
        stepper_layout = QHBoxLayout(self._stepper)
        stepper_layout.setContentsMargins(1, 1, 1, 1)
        stepper_layout.setSpacing(0)
        stepper_layout.addWidget(minus)
        stepper_layout.addWidget(self._stepper_line())
        stepper_layout.addWidget(self.priority_spin)
        stepper_layout.addWidget(self._stepper_line())
        stepper_layout.addWidget(plus)

        self._lock_icon = QLabel()
        self._lock_icon.setPixmap(pixmap("lock", "#6B6F7A", 16))
        self.priority_note = QLabel()
        self.priority_note.setObjectName("priorityNote")

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(self._stepper)
        row.addSpacing(8)
        row.addWidget(self._lock_icon)
        row.addWidget(self.priority_note)
        row.addStretch(1)
        return row

    @staticmethod
    def _stepper_line() -> QFrame:
        line = QFrame()
        line.setObjectName("stepperLine")
        line.setFixedWidth(1)
        return line

    def _build_footer(self) -> QWidget:
        self.delete_button = QPushButton("  Delete")
        self.delete_button.setObjectName("deleteButton")
        self.delete_button.setIcon(icon("trash", "#D32F2F", 18))
        self.delete_button.setIconSize(QSize(18, 18))
        self.delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_button.setAutoDefault(False)
        self.delete_button.clicked.connect(self._delete)
        self.delete_button.setHidden(self._task is None)
        if self._task and self._task.stage == Stage.IN_PROCESS:
            self.delete_button.setEnabled(False)
            self.delete_button.setToolTip(_DELETE_LOCKED)

        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("cancelButton")
        cancel_button.setAutoDefault(False)
        cancel_button.clicked.connect(self.reject)

        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("saveButton")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._save)

        footer = QWidget()
        footer.setObjectName("footer")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(26, 14, 26, 18)
        layout.setSpacing(12)
        layout.addWidget(self.delete_button)
        layout.addStretch(1)
        layout.addWidget(cancel_button)
        layout.addWidget(self.save_button)
        return footer

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.FocusIn:
            for editor in (self.details_editor, self.usable_data_editor):
                if watched is editor.text_edit:
                    self._focused_editor = editor
                    self._update_split()
        return super().eventFilter(watched, event)

    def _update_split(self) -> None:
        if self._focused_editor is self.details_editor:
            split = _SPLIT_FOR_DETAILS
        elif self._focused_editor is self.usable_data_editor:
            split = _SPLIT_FOR_USABLE_DATA
        else:
            split = self._split_by_content()
        self._content.setStretchFactor(self.details_editor, split[0])
        self._content.setStretchFactor(self.usable_data_editor, split[1])

    def _split_by_content(self) -> tuple[int, int]:
        has_details = bool(self.details_editor.text_edit.toPlainText().strip())
        has_usable_data = bool(self.usable_data_editor.text_edit.toPlainText().strip())
        if has_details and has_usable_data:
            return _SPLIT_EVEN
        if has_usable_data:
            return _SPLIT_FOR_USABLE_DATA
        return _SPLIT_FOR_DETAILS

    def _priority_lock_reason(self) -> str | None:
        if self._task and self._task.stage == Stage.DONE:
            return _LOCKED_BY_DONE
        if any(f.line_edit.text().strip() for f in (self.due_date_field, self.deadline_field)):
            return _LOCKED_BY_DATES
        return None

    def _update_priority_lock(self) -> None:
        reason = self._priority_lock_reason()
        self._stepper.setEnabled(reason is None)
        self.priority_note.setText(reason or "")
        self.priority_note.setHidden(reason is None)
        self._lock_icon.setHidden(reason is None)

    def _save(self) -> None:
        try:
            fields = dict(
                title=self.title_edit.text().strip(),
                details=self.details_editor.markdown(),
                usable_data=self.usable_data_editor.markdown(),
                due_date=self._read_date(self.due_date_field, "Due date"),
                deadline=self._read_date(self.deadline_field, "Deadline"),
                priority=None if self._priority_lock_reason() else self.priority_spin.value(),
            )
            if self._require_date and not (fields["due_date"] or fields["deadline"]):
                raise InvalidTask(_NEEDS_A_DATE)
            if self._task:
                self._board.edit_task(self._task.id, **fields)
            else:
                self._board.add_task(**fields)
        except InvalidTask as error:
            self.error_label.setText(str(error))
            return
        self.accept()

    def _delete(self) -> None:
        answer = QMessageBox.question(self, "Delete Task", f"Delete “{self._task.title}”? This cannot be undone.")
        if answer == QMessageBox.StandardButton.Yes:
            self._board.delete_task(self._task.id)
            self.accept()

    @staticmethod
    def _read_date(field: DateField, name: str):
        try:
            return field.date()
        except ValueError:
            raise InvalidTask(f"{name} must be a date in dd/mm/yyyy format.") from None
