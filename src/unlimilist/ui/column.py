"""A Column on the Board: one Stage, its Someday cards aligned left and Time-limited cards aligned right."""

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from unlimilist.domain import LaneKind, Stage, Task, Urgency
from unlimilist.ui.card import CardWidget, decode_drag
from unlimilist.ui.styling import card_fill

# While the Tag filter hides some cards, a drop position is ambiguous: a Task moved in from another Stage
# goes to the bottom (rank 999 means the bottom), and reordering within the Stage is refused.
_BOTTOM_INDEX = 998
_FILTERED_REORDER_HINT = "Clear the Tag filter to reorder"
_CARD_SHARE = 3  # a card takes 3 parts of 4, i.e. 75% of the Column width
_GAP_SHARE = 1

_DROP_HINTS = {
    LaneKind.SOMEDAY: "Drop as Someday",
    LaneKind.TIME_LIMITED: "Drop as Time-limited",
}
_CONVERSION_HINTS = {
    LaneKind.SOMEDAY: "Drop as Someday — clears the dates",
    LaneKind.TIME_LIMITED: "Drop as Time-limited — asks for a date",
}


class ColumnWidget(QFrame):
    cardClicked = Signal(str)
    cardMenuRequested = Signal(str, QPoint)
    # task id, target Stage, target LaneKind (None for Done), drop rank index among the Someday cards,
    # and the drop point on screen
    taskDropped = Signal(str, object, object, int, QPoint)

    def __init__(self, stage: Stage, title: str, top_widget: QWidget | None = None, parent=None):
        super().__init__(parent)
        self.stage = stage
        self.setObjectName("stage")
        self.setAcceptDrops(True)

        header = QLabel(title)
        header.setObjectName("stageHeader")

        self._someday_count = QLabel()
        self._someday_count.setObjectName("laneHeader")
        self._time_limited_count = QLabel()
        self._time_limited_count.setObjectName("laneHeader")
        counts = QHBoxLayout()
        counts.setContentsMargins(6, 0, 6, 0)
        counts.addWidget(self._someday_count)
        counts.addStretch(1)
        counts.addWidget(self._time_limited_count)
        self._time_limited_count.setHidden(stage == Stage.DONE)

        self._hint = QLabel()
        self._hint.setObjectName("laneHint")
        self._hint.hide()

        self._cards: list[CardWidget] = []
        self._rows: list[QWidget] = []
        self._filtered = False
        self._task_ids: set[str] = set()
        self._placeholders: list[QFrame] = []
        self._container = QWidget()
        self._container.setObjectName("laneBody")
        self._stack = QVBoxLayout(self._container)
        self._stack.setContentsMargins(8, 6, 8, 12)
        self._stack.setSpacing(10)
        self._stack.addStretch(1)
        self._indicator = QFrame()
        self._indicator.setObjectName("dropIndicator")
        self._indicator.setFixedHeight(3)
        self._indicator.hide()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self._container)

        self._body = QFrame()
        self._body.setObjectName("lane")
        self._set_drop_side(None)
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(4, 6, 4, 4)
        body_layout.setSpacing(4)
        body_layout.addLayout(counts)
        body_layout.addWidget(self._hint)
        body_layout.addWidget(scroll, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(header)
        if top_widget is not None:
            layout.addWidget(top_widget)
        layout.addWidget(self._body, 1)

    def drop_hint(self) -> str:
        """The hint shown while a Task is dragged over this Column, or "" when there is none."""
        return "" if self._hint.isHidden() else self._hint.text()

    def cards(self) -> list[CardWidget]:
        """Cards in the order shown, top to bottom."""
        return list(self._cards)

    def show_placeholders(self, count: int) -> None:
        """Grey tiles standing in for cards while the Tasks load; set_tasks replaces them."""
        self._clear_placeholders()
        for _ in range(count):
            tile = QFrame()
            tile.setObjectName("placeholderTile")
            tile.setFixedHeight(62)
            self._stack.insertWidget(self._stack.count() - 1, tile)
            self._placeholders.append(tile)

    def placeholder_count(self) -> int:
        return len(self._placeholders)

    def _clear_placeholders(self) -> None:
        for tile in self._placeholders:
            tile.setParent(None)
            tile.deleteLater()
        self._placeholders = []

    def lane_headers(self) -> tuple[str, str | None]:
        """The Lane header texts; Done has only one."""
        return self._someday_count.text(), None if self.stage == Stage.DONE else self._time_limited_count.text()

    def set_tasks(self, tasks: list[Task], urgencies: list[Urgency], shown: set[str] | None = None) -> None:
        """Show `tasks` in order, or only those whose id is in `shown` while the Tag filter is on.

        A card keeps the shade of its place among all of `tasks`, so filtering never recolours it.
        """
        self._clear_placeholders()
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._cards, self._rows = [], []
        self._filtered = shown is not None
        self._task_ids = {t.id for t in tasks}
        for index, (task, urgency) in enumerate(zip(tasks, urgencies)):
            if shown is not None and task.id not in shown:
                continue
            kind = None if self.stage == Stage.DONE else task.kind
            card = CardWidget(task, urgency, card_fill(self.stage, kind, index, len(tasks)))
            card.clicked.connect(self.cardClicked)
            card.menuRequested.connect(self.cardMenuRequested)
            row = self._row_for(card)
            self._stack.insertWidget(self._stack.count() - 1, row)
            self._cards.append(card)
            self._rows.append(row)
        visible = [c.task for c in self._cards]
        if self.stage == Stage.DONE:
            self._someday_count.setText(f"COMPLETED  ·  {_count(visible, tasks, self._filtered)}")
        else:
            someday = [t for t in tasks if t.kind == LaneKind.SOMEDAY]
            time_limited = [t for t in tasks if t.kind == LaneKind.TIME_LIMITED]
            shown_someday = [t for t in visible if t.kind == LaneKind.SOMEDAY]
            shown_time_limited = [t for t in visible if t.kind == LaneKind.TIME_LIMITED]
            self._someday_count.setText(f"SOMEDAY  ·  {_count(shown_someday, someday, self._filtered)}")
            self._time_limited_count.setText(
                f"TIME-LIMITED  ·  {_count(shown_time_limited, time_limited, self._filtered)}"
            )

    def _row_for(self, card: CardWidget) -> QWidget:
        row = QWidget()
        row.setObjectName("cardRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        if self.stage == Stage.DONE:
            layout.addWidget(card)
        elif card.task.kind == LaneKind.SOMEDAY:
            layout.addWidget(card, _CARD_SHARE)
            layout.addStretch(_GAP_SHARE)
        else:
            layout.addStretch(_GAP_SHARE)
            layout.addWidget(card, _CARD_SHARE)
        return row

    # Drag and drop

    def _side(self, pos: QPoint) -> LaneKind | None:
        if self.stage == Stage.DONE:
            return None
        return LaneKind.SOMEDAY if pos.x() < self.width() / 2 else LaneKind.TIME_LIMITED

    def dragEnterEvent(self, event):
        if decode_drag(event.mimeData()) is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self._update_drag(event)

    def dragMoveEvent(self, event):
        if decode_drag(event.mimeData()) is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self._update_drag(event)

    def dragLeaveEvent(self, event):
        self._end_drag()

    def dropEvent(self, event):
        dragged = decode_drag(event.mimeData())
        self._end_drag()
        if dragged is None:
            event.ignore()
            return
        if self._reorder_refused(dragged.task_id):
            event.ignore()
            return
        event.acceptProposedAction()
        pos = event.position().toPoint()
        index = _BOTTOM_INDEX if self._filtered else self._someday_index(dragged.task_id, pos)
        self.taskDropped.emit(dragged.task_id, self.stage, self._side(pos), index, self.mapToGlobal(pos))

    def _reorder_refused(self, task_id: str) -> bool:
        return self._filtered and task_id in self._task_ids

    def _update_drag(self, event) -> None:
        task_id, kind, unfinished = decode_drag(event.mimeData())
        pos = event.position().toPoint()
        side = self._side(pos)
        if self.stage == Stage.DONE and unfinished:
            # The Board will refuse it; say why rather than invite the drop.
            self._set_drop_side("blocked")
            self._hint.setText(f"{unfinished} unfinished {'subtask' if unfinished == 1 else 'subtasks'}")
            self._hint.show()
            return
        if self._reorder_refused(task_id):
            self._set_drop_side("blocked")
            self._hint.setText(_FILTERED_REORDER_HINT)
            self._hint.show()
            self._indicator.hide()
            return
        self._set_drop_side(side or "all")
        if side is None:
            self._hint.hide()
        else:
            self._hint.setText((_DROP_HINTS if side == kind else _CONVERSION_HINTS)[side])
            self._hint.show()
        if side == LaneKind.SOMEDAY and not self._filtered:
            self._show_indicator(task_id, self._someday_index(task_id, pos))
        else:
            self._indicator.hide()

    def _someday_cards(self, task_id: str) -> list[CardWidget]:
        return [c for c in self._cards if c.task.kind == LaneKind.SOMEDAY and c.task.id != task_id]

    def _someday_index(self, task_id: str, pos: QPoint) -> int:
        """Where a drop at `pos` lands, counted among the other Someday cards."""
        y = self._container.mapFrom(self, pos).y()
        others = self._someday_cards(task_id)
        for index, card in enumerate(others):
            if y < card.parentWidget().geometry().center().y():
                return index
        return len(others)

    def _show_indicator(self, task_id: str, index: int) -> None:
        others = self._someday_cards(task_id)
        self._stack.removeWidget(self._indicator)
        if index < len(others):
            position = self._stack.indexOf(others[index].parentWidget())
        elif others:
            position = self._stack.indexOf(others[-1].parentWidget()) + 1
        else:
            position = 0
        self._stack.insertWidget(position, self._indicator)
        self._indicator.show()

    def _end_drag(self) -> None:
        self._set_drop_side(None)
        self._hint.hide()
        self._indicator.hide()
        self._stack.removeWidget(self._indicator)

    def _set_drop_side(self, side) -> None:
        value = {None: "", "all": "all", "blocked": "blocked", LaneKind.SOMEDAY: "left", LaneKind.TIME_LIMITED: "right"}[
            side
        ]
        self._body.setProperty("dropSide", value)
        self._body.style().unpolish(self._body)
        self._body.style().polish(self._body)


def _count(shown: list[Task], everything: list[Task], filtered: bool) -> str:
    """"5", or "2 of 5" while the Tag filter hides some Tasks."""
    return f"{len(shown)} of {len(everything)}" if filtered else str(len(everything))
