"""The main window: sidebar on the left, Board on the right."""

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QCursor, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QWidget,
)

from unlimilist import __version__
from unlimilist.board import Board
from unlimilist.domain import LaneKind, Stage, UnfinishedSubtasks
from unlimilist.ui.balloon import Balloon
from unlimilist.ui.board_view import BoardView
from unlimilist.ui.icons import app_icon
from unlimilist.ui.sidebar import Sidebar
from unlimilist.ui.task_dialog import TaskDialog

_TEN_MINUTES_MS = 10 * 60 * 1000
_APP_NAME = "UnlimiList"
_VERSION = ".".join(__version__.split(".")[:2])  # "1.4.0" is shown as "1.4"
_DEFAULT_SIZE = (1500, 950)


class MainWindow(QMainWindow):
    def __init__(self, board: Board, warnings: list[str] | None = None, parent=None):
        super().__init__(parent)
        self._board = board
        self.setWindowTitle(f"{_APP_NAME} {_VERSION}")
        self.setWindowIcon(app_icon())
        self._open_at_default_size()

        # The Tag filter (case-folded Tag keys) starts empty on every launch.
        self._tag_filter: frozenset[str] = frozenset()
        self.sidebar = Sidebar()
        self.sidebar.tagClicked.connect(self.toggle_tag)
        self.sidebar.clearClicked.connect(self.clear_tag_filter)
        self.sidebar.everythingClicked.connect(self.clear_tag_filter)

        self.balloon = Balloon(self)
        self.board_view = BoardView(board)
        self.board_view.cardClicked.connect(self.open_task)
        self.board_view.taskAdded.connect(self._task_created)
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
        toolbar.addWidget(self._build_title())
        toolbar.addAction(new_task)

        if warnings:
            self.statusBar().showMessage(f"{len(warnings)} task file(s) could not be read — hover for details")
            self.statusBar().setToolTip("\n".join(warnings))

        # Urgency depends on today's date, so keep it current while the app stays open.
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self.refresh)
        self._clock_timer.start(_TEN_MINUTES_MS)
        self.refresh()

    def _open_at_default_size(self) -> None:
        width, height = _DEFAULT_SIZE
        screen = self.screen().availableGeometry()
        self.resize(min(width, screen.width()), min(height, screen.height()))

    def _build_title(self) -> QWidget:
        """The app's name with its version in a small red circle."""
        self.app_title = QLabel(_APP_NAME)
        self.app_title.setObjectName("appTitle")
        self.version_badge = QLabel(_VERSION)
        self.version_badge.setObjectName("versionBadge")
        self.version_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_badge.setFixedSize(26, 26)

        title = QWidget()
        title.setObjectName("titleBlock")
        layout = QHBoxLayout(title)
        layout.setContentsMargins(6, 0, 18, 0)
        layout.setSpacing(5)
        layout.addWidget(self.app_title)
        layout.addWidget(self.version_badge, 0, Qt.AlignmentFlag.AlignTop)
        return title

    def refresh(self) -> None:
        """Redraw the sidebar's Tags and the Board. A selected Tag that no Task has any more is dropped."""
        tags = self._board.tags()
        self._tag_filter = self._tag_filter & {name.casefold() for name, _ in tags}
        self.sidebar.set_tags(tags, self._tag_filter)
        self.board_view.set_tag_filter(self._tag_filter)

    def toggle_tag(self, key: str) -> None:
        self._tag_filter = self._tag_filter ^ {key}
        self.refresh()

    def clear_tag_filter(self) -> None:
        self._tag_filter = frozenset()
        self.refresh()

    def _task_created(self) -> None:
        """Creating a Task clears the Tag filter, so the new Task is never hidden."""
        self.clear_tag_filter()

    def new_task(self) -> None:
        if TaskDialog(self._board, parent=self).exec() == QDialog.DialogCode.Accepted:
            self._task_created()
        else:
            self.refresh()

    def open_task(self, task_id: str) -> None:
        TaskDialog(self._board, self._board.task(task_id), parent=self).exec()
        self.refresh()

    def handle_drop(
        self, task_id: str, stage: Stage, kind: LaneKind | None, index: int, at: QPoint | None = None
    ) -> None:
        """Move a dropped Task; dropping onto the other kind of Lane converts it first.

        A Task the Board refuses to complete stays put, and a balloon at `at` says why.
        """
        task = self._board.task(task_id)
        if stage == Stage.DONE:
            try:
                self._board.move_task(task_id, stage)
            except UnfinishedSubtasks as refused:
                self.balloon.show_at(at or QCursor.pos(), str(refused))
        elif kind == task.kind:
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
        self.refresh()
