"""The main window: sidebar on the left, Board on the right."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QWidget,
)

from unlimilist.board import Board
from unlimilist.domain import LaneKind, Stage
from unlimilist.ui.board_view import BoardView
from unlimilist.ui.task_dialog import TaskDialog

_TEN_MINUTES_MS = 10 * 60 * 1000


class MainWindow(QMainWindow):
    def __init__(self, board: Board, warnings: list[str] | None = None, parent=None):
        super().__init__(parent)
        self._board = board
        self.setWindowTitle("Unlimilist")
        self.resize(1280, 800)

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(190)
        self.sidebar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        everything = QListWidgetItem("Everything")
        self.sidebar.addItem(everything)
        placeholder = QListWidgetItem("TBD")
        placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
        self.sidebar.addItem(placeholder)
        self.sidebar.setCurrentItem(everything)

        self.board_view = BoardView(board)
        self.board_view.cardClicked.connect(self.open_task)
        # Queued: a drop may open a modal dialog, which must not run inside the drag loop.
        self.board_view.taskDropped.connect(self.handle_drop, Qt.ConnectionType.QueuedConnection)

        central = QWidget()
        central.setObjectName("central")
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.board_view, 1)
        self.setCentralWidget(central)

        new_task = QAction("＋ New Task", self)
        new_task.setShortcut(QKeySequence.StandardKey.New)
        new_task.triggered.connect(self.new_task)
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        toolbar.addAction(new_task)

        if warnings:
            self.statusBar().showMessage(f"{len(warnings)} task file(s) could not be read — hover for details")
            self.statusBar().setToolTip("\n".join(warnings))

        # Urgency depends on today's date, so keep it current while the app stays open.
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self.board_view.refresh)
        self._clock_timer.start(_TEN_MINUTES_MS)

    def new_task(self) -> None:
        TaskDialog(self._board, parent=self).exec()
        self.board_view.refresh()

    def open_task(self, task_id: str) -> None:
        TaskDialog(self._board, self._board.task(task_id), parent=self).exec()
        self.board_view.refresh()

    def handle_drop(self, task_id: str, stage: Stage, kind: LaneKind | None, index: int) -> None:
        """Move a dropped Task; dropping onto the other kind of Lane converts it first."""
        task = self._board.task(task_id)
        if stage == Stage.DONE or kind == task.kind:
            self._board.move_task(task_id, stage, priority=index + 1)
        elif kind == LaneKind.TIME_LIMITED:
            dialog = TaskDialog(self._board, task, parent=self, require_date=True)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._board.move_task(task_id, stage)
        else:
            answer = QMessageBox.question(
                self,
                "Make it a Someday Task?",
                f"Moving “{task.title}” to Someday clears its Due date and Deadline. Continue?",
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._board.edit_task(task_id, due_date=None, deadline=None)
                self._board.move_task(task_id, stage, priority=index + 1)
        self.board_view.refresh()
