"""The Board: three Stage columns, with Someday and Time-limited Lanes in Inbox and In Process."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from unlimilist.board import Board
from unlimilist.domain import LaneKind, Stage
from unlimilist.ui.lane import LaneWidget

_STAGE_TITLES = {Stage.INBOX: "Inbox", Stage.IN_PROCESS: "In Process", Stage.DONE: "Done"}
_LANE_TITLES = {LaneKind.SOMEDAY: "Someday", LaneKind.TIME_LIMITED: "Time-limited"}


class BoardView(QWidget):
    cardClicked = Signal(str)
    taskDropped = Signal(str, object, object, int)

    def __init__(self, board: Board, parent=None):
        super().__init__(parent)
        self._board = board
        self._lanes: dict[tuple[Stage, LaneKind | None], LaneWidget] = {}

        self.quick_add = QLineEdit()
        self.quick_add.setObjectName("quickAdd")
        self.quick_add.setPlaceholderText("＋ Quick add to Inbox — type a title, press Enter")
        self.quick_add.returnPressed.connect(self._quick_add)

        columns = QHBoxLayout(self)
        columns.setContentsMargins(12, 12, 12, 12)
        columns.setSpacing(12)
        for stage in Stage:
            columns.addWidget(self._build_column(stage), 1)
        self.refresh()

    def lane_widget(self, stage: Stage, kind: LaneKind | None = None) -> LaneWidget:
        return self._lanes[(stage, None if stage == Stage.DONE else kind)]

    def refresh(self) -> None:
        for (stage, kind), lane in self._lanes.items():
            tasks = self._board.lane(stage, kind)
            lane.set_tasks(tasks, [self._board.urgency(t.id) for t in tasks])

    def _build_column(self, stage: Stage) -> QFrame:
        column = QFrame()
        column.setObjectName("stage")
        layout = QVBoxLayout(column)
        layout.setContentsMargins(8, 10, 8, 8)
        layout.setSpacing(8)
        header = QLabel(_STAGE_TITLES[stage])
        header.setObjectName("stageHeader")
        layout.addWidget(header)
        if stage == Stage.INBOX:
            layout.addWidget(self.quick_add)
        kinds = [None] if stage == Stage.DONE else [LaneKind.SOMEDAY, LaneKind.TIME_LIMITED]
        for kind in kinds:
            lane = LaneWidget(stage, kind, _LANE_TITLES.get(kind, "Completed"))
            lane.cardClicked.connect(self.cardClicked)
            lane.taskDropped.connect(self.taskDropped)
            self._lanes[(stage, kind)] = lane
            layout.addWidget(lane, 1)
        return column

    def _quick_add(self) -> None:
        title = self.quick_add.text().strip()
        if not title:
            return
        self._board.add_task(title)
        self.quick_add.clear()
        self.refresh()
