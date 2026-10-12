"""A Column on the Board: one Stage, its Someday cards aligned left and Time-limited cards aligned right."""

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from unlimilist.domain import LaneKind, Stage, Task, Urgency
from unlimilist.ui.card import CardWidget, decode_drag
from unlimilist.ui.styling import card_fill

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
    # task id, target Stage, target LaneKind (None for Done), drop rank index among the Someday cards
    taskDropped = Signal(str, object, object, int)

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

    def cards(self) -> list[CardWidget]:
        """Cards in the order shown, top to bottom."""
        return list(self._cards)

    def set_tasks(self, tasks: list[Task], urgencies: list[Urgency]) -> None:
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._cards, self._rows = [], []
        for index, (task, urgency) in enumerate(zip(tasks, urgencies)):
            kind = None if self.stage == Stage.DONE else task.kind
            card = CardWidget(task, urgency, card_fill(self.stage, kind, index, len(tasks)))
            card.clicked.connect(self.cardClicked)
            row = self._row_for(card)
            self._stack.insertWidget(self._stack.count() - 1, row)
            self._cards.append(card)
            self._rows.append(row)
        someday = sum(1 for t in tasks if t.kind == LaneKind.SOMEDAY)
        if self.stage == Stage.DONE:
            self._someday_count.setText(f"COMPLETED  ·  {len(tasks)}")
        else:
            self._someday_count.setText(f"SOMEDAY  ·  {someday}")
            self._time_limited_count.setText(f"TIME-LIMITED  ·  {len(tasks) - someday}")

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
        task_id, _ = dragged
        event.acceptProposedAction()
        pos = event.position().toPoint()
        self.taskDropped.emit(task_id, self.stage, self._side(pos), self._someday_index(task_id, pos))

    def _update_drag(self, event) -> None:
        task_id, kind = decode_drag(event.mimeData())
        pos = event.position().toPoint()
        side = self._side(pos)
        self._set_drop_side(side or "all")
        if side is None:
            self._hint.hide()
        else:
            self._hint.setText((_DROP_HINTS if side == kind else _CONVERSION_HINTS)[side])
            self._hint.show()
        if side == LaneKind.SOMEDAY:
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
        value = {None: "", "all": "all", LaneKind.SOMEDAY: "left", LaneKind.TIME_LIMITED: "right"}[side]
        self._body.setProperty("dropSide", value)
        self._body.style().unpolish(self._body)
        self._body.style().polish(self._body)
