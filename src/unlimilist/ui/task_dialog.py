"""The modal dialog that creates or edits a Task."""

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from unlimilist.board import Board
from unlimilist.domain import InvalidTask, LaneKind, Stage, Task
from unlimilist.ui.date_field import DateField
from unlimilist.ui.rich_text import RichTextEditor


class TaskDialog(QDialog):
    def __init__(self, board: Board, task: Task | None = None, parent=None, require_date: bool = False):
        """`require_date` is used when a Someday Task is dropped on a Time-limited Lane."""
        super().__init__(parent)
        self._board = board
        self._task = task
        self._require_date = require_date
        self.setWindowTitle("Edit Task" if task else "New Task")
        self.setModal(True)
        self.resize(560, 620)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("What needs doing?")
        self.details_editor = RichTextEditor("Describe the Task…")
        self.usable_data_editor = RichTextEditor("Links, snippets, reference info…")
        self.due_date_field = DateField()
        self.deadline_field = DateField()
        self.priority_spin = QSpinBox()
        self.priority_spin.setMinimum(1)
        self.priority_spin.setToolTip("1 is the top of the Lane")

        form = QFormLayout()
        self._form = form
        form.addRow("Title *", self.title_edit)
        form.addRow("Details", self.details_editor)
        form.addRow("Usable data", self.usable_data_editor)
        form.addRow("Due date", self.due_date_field)
        form.addRow("Deadline", self.deadline_field)
        form.addRow("Priority", self.priority_spin)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #E53935;")
        self.error_label.setWordWrap(True)
        if require_date:
            self.error_label.setText("Add a Due date or Deadline to make this a Time-limited Task.")

        self.save_button = QPushButton("Save")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._save)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self._delete)
        self.delete_button.setHidden(task is None)
        buttons = QHBoxLayout()
        buttons.addWidget(self.delete_button)
        buttons.addStretch(1)
        buttons.addWidget(cancel_button)
        buttons.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addLayout(buttons)

        if task:
            self.title_edit.setText(task.title)
            self.details_editor.set_markdown(task.details)
            self.usable_data_editor.set_markdown(task.usable_data)
            self.due_date_field.set_date(task.due_date)
            self.deadline_field.set_date(task.deadline)
        self._init_priority()
        self.due_date_field.dateChanged.connect(self._update_priority_visibility)
        self.deadline_field.dateChanged.connect(self._update_priority_visibility)
        self._update_priority_visibility()

    def _init_priority(self) -> None:
        """Range 1..N for a Task already ranked in its Lane, 1..N+1 (defaulting to the bottom) otherwise."""
        stage = self._task.stage if self._task else Stage.INBOX
        lane_size = len(self._board.lane(stage, LaneKind.SOMEDAY))
        if self._task and self._task.priority is not None:
            self.priority_spin.setMaximum(lane_size)
            self.priority_spin.setValue(self._task.priority)
        else:
            self.priority_spin.setMaximum(lane_size + 1)
            self.priority_spin.setValue(lane_size + 1)

    def _priority_applies(self) -> bool:
        if self._task and self._task.stage == Stage.DONE:
            return False
        empty = [f.line_edit.text().strip() == "" for f in (self.due_date_field, self.deadline_field)]
        return all(empty)

    def _update_priority_visibility(self) -> None:
        self._form.setRowVisible(self.priority_spin, self._priority_applies())

    def _save(self) -> None:
        try:
            fields = dict(
                title=self.title_edit.text().strip(),
                details=self.details_editor.markdown(),
                usable_data=self.usable_data_editor.markdown(),
                due_date=self._read_date(self.due_date_field, "Due date"),
                deadline=self._read_date(self.deadline_field, "Deadline"),
                priority=self.priority_spin.value() if self._priority_applies() else None,
            )
            if self._require_date and not (fields["due_date"] or fields["deadline"]):
                raise InvalidTask("Add a Due date or Deadline to make this a Time-limited Task.")
            if self._task:
                self._board.edit_task(self._task.id, **fields)
            else:
                self._board.add_task(**fields)
        except InvalidTask as error:
            self.error_label.setText(str(error))
            return
        self.accept()

    def _delete(self) -> None:
        answer = QMessageBox.question(
            self, "Delete Task", f"Delete “{self._task.title}”? This cannot be undone."
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._board.delete_task(self._task.id)
            self.accept()

    @staticmethod
    def _read_date(field: DateField, name: str):
        try:
            return field.date()
        except ValueError:
            raise InvalidTask(f"{name} must be a date in dd/mm/yyyy format.") from None
