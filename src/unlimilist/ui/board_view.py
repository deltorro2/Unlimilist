"""The Board: one Column per Stage. Done is narrower."""

from PySide6.QtCore import QPoint, Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QWidget

from unlimilist.board import Board
from unlimilist.domain import Stage
from unlimilist.ui.column import ColumnWidget

_STAGE_TITLES = {Stage.INBOX: "Inbox", Stage.IN_PROCESS: "In Process", Stage.DONE: "Done"}
# Done is 40% narrower than the other Columns.
_STRETCH = {Stage.INBOX: 5, Stage.IN_PROCESS: 5, Stage.DONE: 3}


class BoardView(QWidget):
    cardClicked = Signal(str)
    taskAdded = Signal()
    taskDropped = Signal(str, object, object, int, QPoint)

    def __init__(self, board: Board, parent=None):
        super().__init__(parent)
        self._board = board
        self._columns: dict[Stage, ColumnWidget] = {}
        self._tag_filter: frozenset[str] = frozenset()

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

    def set_board(self, board: Board) -> None:
        """Show `board` from the next refresh on."""
        self._board = board

    def show_placeholders(self, count: int = 4) -> None:
        for column in self._columns.values():
            column.show_placeholders(count)

    def set_tag_filter(self, tag_filter: frozenset[str]) -> None:
        """Show only Tasks with any of these Tags (case-folded keys); empty shows every Task."""
        self._tag_filter = tag_filter
        self.refresh()

    def refresh(self) -> None:
        for stage, column in self._columns.items():
            tasks = self._board.column(stage)
            shown = {t.id for t in tasks if t.matches_tag_filter(self._tag_filter)} if self._tag_filter else None
            column.set_tasks(tasks, [self._board.urgency(t.id) for t in tasks], shown)

    def _quick_add(self) -> None:
        title = self.quick_add.text().strip()
        if not title:
            return
        self._board.add_task(title)
        self.quick_add.clear()
        self.refresh()
        self.taskAdded.emit()
