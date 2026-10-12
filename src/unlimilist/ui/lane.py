"""A Lane on the Board: a titled, scrollable stack of cards that accepts dropped Tasks."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from unlimilist.domain import LaneKind, Stage, Task, Urgency
from unlimilist.ui.card import CardWidget, decode_drag
from unlimilist.ui.styling import card_fill

_CONVERSION_HINTS = {
    LaneKind.TIME_LIMITED: "Drop to add a date",
    LaneKind.SOMEDAY: "Drop to clear the dates",
}


class LaneWidget(QFrame):
    cardClicked = Signal(str)
    # task id, target Stage, target LaneKind (None for Done), drop index among the other cards
    taskDropped = Signal(str, object, object, int)

    def __init__(self, stage: Stage, kind: LaneKind | None, title: str, parent=None):
        super().__init__(parent)
        self.stage = stage
        self.kind = kind
        self.setObjectName("lane")
        self.setAcceptDrops(True)
        self._set_highlight(False)

        self._title = title
        self._header = QLabel(title)
        self._header.setObjectName("laneHeader")
        self._hint = QLabel()
        self._hint.setObjectName("laneHint")
        self._hint.hide()

        self._cards: list[CardWidget] = []
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(4)
        layout.addWidget(self._header)
        layout.addWidget(self._hint)
        layout.addWidget(scroll, 1)

    def cards(self) -> list[CardWidget]:
        return list(self._cards)

    def set_tasks(self, tasks: list[Task], urgencies: list[Urgency]) -> None:
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards = []
        for index, (task, urgency) in enumerate(zip(tasks, urgencies)):
            card = CardWidget(task, urgency, card_fill(self.stage, self.kind, index, len(tasks)))
            card.clicked.connect(self.cardClicked)
            self._stack.insertWidget(self._stack.count() - 1, card)
            self._cards.append(card)
        self._header.setText(f"{self._title}  ·  {len(tasks)}")

    # Drag and drop

    def dragEnterEvent(self, event):
        dragged = decode_drag(event.mimeData())
        if dragged is None:
            event.ignore()
            return
        event.acceptProposedAction()
        _, kind = dragged
        self._set_highlight(True)
        converting = self.kind is not None and kind != self.kind
        self._hint.setText(_CONVERSION_HINTS[self.kind] if converting else "")
        self._hint.setVisible(converting)

    def dragMoveEvent(self, event):
        dragged = decode_drag(event.mimeData())
        if dragged is None:
            event.ignore()
            return
        event.acceptProposedAction()
        if self.kind == LaneKind.SOMEDAY:
            task_id, _ = dragged
            index = self._drop_index(task_id, event.position().toPoint())
            self._show_indicator(task_id, index)

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
        self.taskDropped.emit(task_id, self.stage, self.kind, self._drop_index(task_id, event.position().toPoint()))

    def _drop_index(self, task_id: str, lane_pos) -> int:
        """Where the dragged Task would land, counted among the other cards in this Lane."""
        y = self._container.mapFrom(self, lane_pos).y()
        others = [c for c in self._cards if c.task.id != task_id]
        for index, card in enumerate(others):
            if y < card.geometry().center().y():
                return index
        return len(others)

    def _show_indicator(self, task_id: str, index: int) -> None:
        others = [c for c in self._cards if c.task.id != task_id]
        self._stack.removeWidget(self._indicator)
        position = self._stack.indexOf(others[index]) if index < len(others) else self._stack.count() - 1
        self._stack.insertWidget(position, self._indicator)
        self._indicator.show()

    def _end_drag(self) -> None:
        self._set_highlight(False)
        self._hint.hide()
        self._indicator.hide()
        self._stack.removeWidget(self._indicator)

    def _set_highlight(self, on: bool) -> None:
        self.setProperty("dropTarget", on)
        self.style().unpolish(self)
        self.style().polish(self)
