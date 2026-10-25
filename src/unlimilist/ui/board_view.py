"""The Board: one Column per Stage. Done is narrower."""

from PySide6.QtCore import QPoint, Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QWidget

from unlimilist.board import Board
from unlimilist.domain import Stage, StaleLimits
from unlimilist.ui.column import FOLDED_WIDTH, ColumnWidget

_STAGE_TITLES = {Stage.INBOX: "Inbox", Stage.IN_PROCESS: "In Process", Stage.DONE: "Done"}
# Done is 40% narrower than the other Columns.
_STRETCH = {Stage.INBOX: 5, Stage.IN_PROCESS: 5, Stage.DONE: 3}


class BoardView(QWidget):
    cardClicked = Signal(str)
    cardMenuRequested = Signal(str, QPoint)
    taskAdded = Signal(str)  # the new Task's id
    taskDropped = Signal(str, object, object, int, QPoint)
    doneFoldedChanged = Signal(bool)

    def __init__(self, board: Board, parent=None):
        super().__init__(parent)
        self._board = board
        self._columns: dict[Stage, ColumnWidget] = {}
        self._tag_filter: frozenset[str] = frozenset()
        self._stale_limits: StaleLimits | None = StaleLimits()

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
            column.cardMenuRequested.connect(self.cardMenuRequested)
            column.taskDropped.connect(self.taskDropped)
            self._columns[stage] = column
            layout.addWidget(column, _STRETCH[stage])
        self._columns[Stage.DONE].fold_switch.toggled.connect(lambda shown: self.set_done_folded(not shown))
        self.refresh()

    def column_widget(self, stage: Stage) -> ColumnWidget:
        return self._columns[stage]

    def set_board(self, board: Board) -> None:
        """Show `board` from the next refresh on."""
        self._board = board

    def cards(self):
        """Every card on the Board."""
        return [card for column in self._columns.values() for card in column.cards()]

    def highlight(self, task_id: str) -> None:
        """Show where a Task that was just created or moved landed. Only one card is highlighted at a time."""
        for card in self.cards():
            card.stop_highlight()
        for column in self._columns.values():
            if column.reveal(task_id):
                return

    def set_done_folded(self, folded: bool) -> None:
        """Fold Done to a strip, or unfold it, sliding; Inbox and In Process take up the room. Never saved."""
        done = self._columns[Stage.DONE]
        if folded == done.is_folded():
            return
        done.fold_switch.setChecked(not folded)
        done.slide(folded, FOLDED_WIDTH if folded else self._unfolded_done_width())
        self.doneFoldedChanged.emit(folded)

    def _unfolded_done_width(self) -> int:
        """Done's width when the Board's stretch shares the room out again."""
        layout = self.layout()
        margins = layout.contentsMargins()
        room = self.width() - margins.left() - margins.right() - layout.spacing() * (len(self._columns) - 1)
        return round(room * _STRETCH[Stage.DONE] / sum(_STRETCH.values()))

    def set_card_font_size(self, size: int) -> None:
        """Draw the cards' text at Card font size `size` (1 to 5)."""
        for column in self._columns.values():
            column.set_card_font_size(size)
        self.refresh()

    def show_placeholders(self, count: int = 4) -> None:
        for column in self._columns.values():
            column.show_placeholders(count)

    def set_tag_filter(self, tag_filter: frozenset[str]) -> None:
        """Show only Tasks with any of these Tags (case-folded keys); empty shows every Task."""
        self._tag_filter = tag_filter
        self.refresh()

    def set_stale_limits(self, limits: StaleLimits | None) -> None:
        """Mark Tasks that have waited longer than these limits as Stale; None marks none."""
        self._stale_limits = limits
        self.refresh()

    def refresh(self) -> None:
        for stage, column in self._columns.items():
            tasks = self._board.column(stage)
            shown = {t.id for t in tasks if t.matches_tag_filter(self._tag_filter)} if self._tag_filter else None
            stale = {}
            if self._stale_limits is not None:
                stale = {t.id: s for t in tasks if (s := self._board.stale(t.id, self._stale_limits))}
            column.set_tasks(tasks, [self._board.urgency(t.id) for t in tasks], shown, stale)

    def _quick_add(self) -> None:
        title = self.quick_add.text().strip()
        if not title:
            return
        task = self._board.add_task(title)
        self.quick_add.clear()
        self.refresh()
        self.taskAdded.emit(task.id)
