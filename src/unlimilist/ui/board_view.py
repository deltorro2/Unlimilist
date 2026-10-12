"""The Board: one Column per Stage. Done is narrower."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QWidget

from unlimilist.board import Board
from unlimilist.domain import Stage
from unlimilist.ui.column import ColumnWidget

_STAGE_TITLES = {Stage.INBOX: "Inbox", Stage.IN_PROCESS: "In Process", Stage.DONE: "Done"}
# Done is 40% narrower than the other Columns.
_STRETCH = {Stage.INBOX: 5, Stage.IN_PROCESS: 5, Stage.DONE: 3}


class BoardView(QWidget):
    cardClicked = Signal(str)
    taskDropped = Signal(str, object, object, int)

    def __init__(self, board: Board, parent=None):
        super().__init__(parent)
        self._board = board
        self._columns: dict[Stage, ColumnWidget] = {}

        self.quick_add = QLineEdit()
        self.quick_add.setObjectName("quickAdd")
        self.quick_add.setPlaceholderText("＋ Quick add to Inbox — type a title, press Enter")
        self.quick_add.returnPressed.connect(self._quick_add)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        for stage in Stage:
            column = ColumnWidget(stage, _STAGE_TITLES[stage], self.quick_add if stage == Stage.INBOX else None)
            column.cardClicked.connect(self.cardClicked)
            column.taskDropped.connect(self.taskDropped)
            self._columns[stage] = column
            layout.addWidget(column, _STRETCH[stage])
        self.refresh()

    def column_widget(self, stage: Stage) -> ColumnWidget:
        return self._columns[stage]

    def refresh(self) -> None:
        for stage, column in self._columns.items():
            tasks = self._board.column(stage)
            column.set_tasks(tasks, [self._board.urgency(t.id) for t in tasks])

    def _quick_add(self) -> None:
        title = self.quick_add.text().strip()
        if not title:
            return
        self._board.add_task(title)
        self.quick_add.clear()
        self.refresh()
