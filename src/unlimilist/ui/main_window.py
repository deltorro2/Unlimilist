"""The main window: sidebar on the left, then the Board or the Notebook."""

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QEvent, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QAction, QCursor, QKeySequence, QRegion, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QStackedWidget,
    QWidget,
)

from unlimilist import __version__
from unlimilist.board import Board, rank_tags
from unlimilist.domain import LaneKind, Stage, UnfinishedSubtasks
from unlimilist.note_search import NoteSearch
from unlimilist.notebook import Notebook
from unlimilist.notebook_password import MemoryVault, NotebookPassword
from unlimilist.secure import WrongPassword
from unlimilist.ui.app_title import AppTitle
from unlimilist.ui.balloon import Balloon
from unlimilist.ui.board_view import BoardView
from unlimilist.settings import Settings, SettingsStore
from unlimilist.ui.icons import app_icon, icon
from unlimilist.ui.loading import BoardLoader, LoadingScreen
from unlimilist.ui import password_dialogs
from unlimilist.ui.notebook_view import NotebookView
from unlimilist.ui.settings_dialog import SettingsDialog
from unlimilist.ui.sidebar import Sidebar
from unlimilist.ui.task_dialog import TaskDialog

_TEN_MINUTES_MS = 10 * 60 * 1000
_APP_NAME = "UnlimiList"
_VERSION = ".".join(__version__.split(".")[:2])  # "1.4.0" is shown as "1.4"
_DEFAULT_SIZE = (1500, 950)
_TEST_TAG = "TEST"  # shown after the version in a test build
_DELETE_TEXT = "Delete Task"
_DELETE_SELECT_TEXT = "Select Tasks in Inbox or Done"
_DELETE_CONFIRM_TEXT = "Delete"
_MINIMUM_LOADING_MS = 5000  # the loading card shows at least this long on every start


class MainWindow(QMainWindow):
    def __init__(
        self,
        board: Board,
        warnings: list[str] | None = None,
        parent=None,
        settings_store: SettingsStore | None = None,
        test_build: bool = False,
        notebook: Notebook | None = None,
        password: NotebookPassword | None = None,
    ):
        super().__init__(parent)
        self._board = board
        self._notebook = notebook or Notebook()
        # Without one (as in tests) the Notebook password lives only in memory, never in the Keychain.
        self._password = password or NotebookPassword(MemoryVault())
        self._test_build = test_build
        self._interactive = True  # False while the Tasks load
        # Without a store (as in tests) the settings start at their defaults and are not saved.
        self._settings_store = settings_store
        self._settings = settings_store.load() if settings_store else Settings()
        self.setWindowTitle(f"{_APP_NAME} {_VERSION}" + (f" {_TEST_TAG}" if test_build else ""))
        self.setWindowIcon(app_icon())
        self._open_at_default_size()

        # The Tag filter (case-folded Tag keys) starts empty on every launch; the Board and the Notebook share it.
        self._tag_filter: frozenset[str] = frozenset()
        self.sidebar = Sidebar()
        self.sidebar.tagClicked.connect(self.toggle_tag)
        self.sidebar.clearClicked.connect(self.clear_tag_filter)
        self.sidebar.tasksClicked.connect(self.show_tasks)
        self.sidebar.notebookClicked.connect(self.show_notebook)

        self.balloon = Balloon(self)
        self.board_view = BoardView(board)
        self.board_view.set_card_font_size(self._settings.card_font_size)
        self.board_view.cardClicked.connect(self._card_clicked)
        self.board_view.cardMenuRequested.connect(self._show_card_menu)
        self.board_view.taskAdded.connect(self._task_created)
        self.board_view.doneFoldedChanged.connect(self._done_folded)
        # Queued: a drop may open a modal dialog, which must not run inside the drag loop.
        self.board_view.taskDropped.connect(self.handle_drop, Qt.ConnectionType.QueuedConnection)
        self.notebook_view = NotebookView(self._notebook, self._password, self.suggest_tags)
        self.notebook_view.noteCreated.connect(self._note_created)
        self.notebook_view.notesChanged.connect(self.refresh)

        self.views = QStackedWidget()
        self.views.addWidget(self.board_view)
        self.views.addWidget(self.notebook_view)
        central = QWidget()
        central.setObjectName("central")
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.views, 1)
        self.setCentralWidget(central)
        # Show Note lies over the sidebar's Tags: only the Tasks and Notebook items stay uncovered.
        self.note_page = self.notebook_view.note_page
        self.note_page.setParent(central)
        self.note_page.hide()
        self.notebook_view.noteShownChanged.connect(lambda _: self._place_note_page())
        central.installEventFilter(self)

        self.new_task_action = QAction("＋ New Task", self)
        self.new_task_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_task_action.triggered.connect(self.new_task)
        toolbar = self.toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        toolbar.addWidget(self._build_title())
        toolbar.addAction(self.new_task_action)
        # Delete Task mode: choose Inbox and Done Tasks on the Board, then delete them together.
        self._delete_mode = False
        self._marked: set[str] = set()
        self.delete_action = QAction(_DELETE_TEXT, self)
        self.delete_action.triggered.connect(self._delete_pressed)
        toolbar.addAction(self.delete_action)
        toolbar.widgetForAction(self.delete_action).setObjectName("deleteTaskButton")
        # The Notebook's own buttons take the Board's place while it is on screen.
        self.new_note_action = QAction("＋ New Note", self)
        self.new_note_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_note_action.triggered.connect(self.new_note)
        toolbar.addAction(self.new_note_action)
        self.import_action = QAction("Import…", self)
        self.import_action.setToolTip("Import Markdown, text, CSV, Word (.docx) or PDF files as Notes")
        self.import_action.triggered.connect(self.import_notes)
        toolbar.addAction(self.import_action)
        # Settings: a plain gear, alone at the far right.
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        spacer.setStyleSheet("background: transparent;")
        toolbar.addWidget(spacer)
        self.settings_action = QAction(icon("settings", "#7A7F8C", 20, hover_colour="#3A3D45"), "", self)
        self.settings_action.setToolTip("Settings")
        self.settings_action.setShortcut(QKeySequence("Ctrl+,"))  # ⌘, on macOS
        self.settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(self.settings_action)
        toolbar.widgetForAction(self.settings_action).setObjectName("settingsButton")

        # ⌘F: the Notebook search, or Find in Note on a shown Note. Nothing on the Board.
        self.find_shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.Find), self)
        self.find_shortcut.activated.connect(self.find)

        self._show_view_actions()
        self._show_warnings(warnings or [])
        self.loading_screen: LoadingScreen | None = None
        self._loader: BoardLoader | None = None

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
        """The app's name, its L in a red ring, then the version in red."""
        self.app_title = AppTitle(_APP_NAME, _VERSION, tag=_TEST_TAG if self._test_build else None)
        self.app_title.setObjectName("appTitle")

        title = QWidget()
        title.setObjectName("titleBlock")
        layout = QHBoxLayout(title)
        layout.setContentsMargins(6, 0, 18, 0)
        layout.addWidget(self.app_title, 0, Qt.AlignmentFlag.AlignVCenter)
        return title

    def load_from(self, folder: Path, minimum_ms: int = _MINIMUM_LOADING_MS, notes_folder: Path | None = None) -> None:
        """Load the Tasks in `folder` (and the Notes in `notes_folder`) in the background, behind the loading card.
        The card stays at least `minimum_ms`, then fades out and the loaded Board takes over."""
        self.board_view.show_placeholders()
        self._set_interactive(False)
        self.loading_screen = LoadingScreen(self)
        self._minimum_ms = minimum_ms
        self._loading_started = QElapsedTimer()
        self._loading_started.start()
        self._loader = BoardLoader(folder, notes_folder)
        # Bound methods, so Qt drops the calls if this window is gone before loading ends.
        self._loader.loaded.connect(self._loaded)
        self._loader.failed.connect(self._loading_failed)
        self._loader.start()

    def _loaded(self, board: Board, notes: tuple[Notebook, NoteSearch] | None, warnings: list[str]) -> None:
        wait = max(0, self._minimum_ms - self._loading_started.elapsed())
        QTimer.singleShot(wait, self, lambda: self._finish_loading(board, notes, warnings))

    def _loading_failed(self, error: str) -> None:
        self.loading_screen.show_error(f"Couldn't open your Tasks: {error}")

    def _finish_loading(self, board: Board, notes: tuple[Notebook, NoteSearch] | None, warnings: list[str]) -> None:
        self._board = board
        if notes is not None:
            self._notebook, search = notes
            self.notebook_view.set_notebook(self._notebook, search)
        self._show_warnings(warnings)
        self._set_interactive(True)  # before the cards exist, so there is little to restyle
        self.board_view.set_board(board)
        self.refresh()

        def gone() -> None:
            self.loading_screen.deleteLater()
            self.loading_screen = None

        self.loading_screen.fade_out(gone)

    def _set_interactive(self, interactive: bool) -> None:
        self._interactive = interactive
        self._show_view_actions()
        self.settings_action.setEnabled(interactive)
        self.centralWidget().setEnabled(interactive)

    def _show_warnings(self, warnings: list[str]) -> None:
        if warnings:
            self.statusBar().showMessage(f"{len(warnings)} file(s) could not be read — hover for details")
            self.statusBar().setToolTip("\n".join(warnings))

    def eventFilter(self, watched, event) -> bool:
        if watched is self.centralWidget() and event.type() == QEvent.Type.Resize:
            self._place_note_page()
        return super().eventFilter(watched, event)

    def _place_note_page(self) -> None:
        """Lay the Note page over the whole central area but the sidebar's view items, or hide it."""
        page = self.note_page
        if self.current_view() != "notebook" or not self.notebook_view.is_showing_note():
            page.hide()
            return
        central = self.centralWidget()
        views = self.sidebar.views
        corner = QRect(views.mapTo(central, QPoint(0, 0)), views.size())
        page.setGeometry(central.rect())
        page.set_corner(corner.right() + 1, corner.bottom() + 1)
        page.setMask(QRegion(central.rect()).subtracted(QRegion(corner)))
        page.show()
        page.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.loading_screen is not None:
            self.loading_screen.setGeometry(self.rect())

    def closeEvent(self, event):
        self.notebook_view.save_now()  # a Note being edited is saved as the app quits
        self.notebook_view.flush_search_index()
        if self._loader is not None:
            self._loader.wait()  # never destroy the loader thread while it runs
        super().closeEvent(event)

    # Settings

    def open_settings(self) -> None:
        dialog = SettingsDialog(self._settings, parent=self, has_password=self._password.exists())
        dialog.cardFontSizeChanged.connect(self._set_card_font_size)
        dialog.changePasswordClicked.connect(self.change_password)
        dialog.exec()

    def change_password(self) -> bool:
        """Change the Notebook password and encrypt every Secured Note again with the new one."""
        answer = password_dialogs.change_password(self, self._password.check)
        if answer is None:
            return False
        old, new = answer
        self.notebook_view.save_now()  # an open Secured Note is saved with the old password first
        try:
            self._notebook.change_password(old, new)
        except WrongPassword:
            QMessageBox.warning(
                self,
                "Change the Notebook password",
                "Some Secured Notes don't open with the current password, so nothing was changed.",
            )
            return False
        self._password.create(new)
        self.statusBar().showMessage("The Notebook password was changed.", 5000)
        return True

    def _set_card_font_size(self, size: int) -> None:
        """Redraw the Board at once and remember the size."""
        self._settings = replace(self._settings, card_font_size=size)
        if self._settings_store is not None:
            self._settings_store.save(self._settings)
        self.board_view.set_card_font_size(size)

    # Tasks and Notebook

    def current_view(self) -> str:
        return "notebook" if self.views.currentWidget() is self.notebook_view else "tasks"

    def find(self) -> None:
        if self.current_view() == "notebook":
            self.notebook_view.find()

    def show_tasks(self) -> None:
        """Back to the Board; a Note being edited is saved and closed, and the Notebook search ends. The Tag
        filter stays."""
        self.notebook_view.leave_note()
        self.notebook_view.clear_search()
        self.notebook_view.show_table()
        self.views.setCurrentWidget(self.board_view)
        self._show_view_actions()
        self.refresh()

    def show_notebook(self) -> None:
        """The Notebook's table (also when a Note was open in it)."""
        self.views.setCurrentWidget(self.notebook_view)
        self._show_view_actions()
        self.refresh()
        self.notebook_view.show_table()

    def _show_view_actions(self) -> None:
        """Each view's own buttons; the other view's are hidden and off, so ⌘N means New Task or New Note."""
        notebook = self.current_view() == "notebook"
        self.sidebar.show_view(notebook)
        for action in (self.new_task_action, self.delete_action):
            action.setVisible(not notebook)
            action.setEnabled(self._interactive and not notebook)
        for action in (self.new_note_action, self.import_action):
            action.setVisible(notebook)
            action.setEnabled(self._interactive and notebook)

    def new_note(self) -> None:
        self.notebook_view.new_note()

    def import_notes(self) -> None:
        self.notebook_view.import_notes()

    def _note_created(self, note_id: str) -> None:
        """Creating a Note clears the Tag filter, so the new Note is never hidden."""
        self.clear_tag_filter()

    def suggest_tags(self, typed: str) -> list[str]:
        """Tags for what was typed, from Tasks and Notes alike: they share Tag names."""
        return rank_tags(typed, self._all_tags())

    def _all_tags(self) -> list[tuple[str, int]]:
        """Every Tag on a Task or a Note, spelled as on the Tasks if both have it, with both counts added up."""
        merged: dict[str, list] = {}
        for name, count in [*self._board.tags(), *self._notebook.tags()]:
            entry = merged.setdefault(name.casefold(), [name, 0])
            entry[1] += count
        return [(name, count) for name, count in merged.values()]

    # Delete Task mode

    def in_delete_mode(self) -> bool:
        return self._delete_mode

    def _delete_pressed(self) -> None:
        if not self._delete_mode:
            self._set_delete_mode(True)
        elif not self._marked:
            self._set_delete_mode(False)
        elif self._confirm_delete(len(self._marked)):
            self._board.delete_tasks(self._marked)
            self._set_delete_mode(False)

    def _set_delete_mode(self, on: bool) -> None:
        self._delete_mode = on
        self._marked = set()
        self.new_task_action.setEnabled(not on)
        self.settings_action.setEnabled(not on)
        self.sidebar.setEnabled(not on)
        self.board_view.quick_add.setEnabled(not on)
        if on:
            self.board_view.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.board_view.unsetCursor()
        self.refresh()

    def _done_folded(self, folded: bool) -> None:
        """Folding Done unmarks its Tasks, so nothing out of sight gets deleted."""
        if folded and self._marked:
            self._marked -= {t.id for t in self._board.column(Stage.DONE)}
            self._show_delete_mode()

    def _card_clicked(self, task_id: str) -> None:
        if not self._delete_mode:
            self.open_task(task_id)
        elif self._board.task(task_id).stage != Stage.IN_PROCESS:
            self._marked ^= {task_id}
            self._show_delete_mode()

    def _show_delete_mode(self) -> None:
        """Mark the chosen cards and set the button text and pointers for the mode."""
        if not self._delete_mode:
            self.delete_action.setText(_DELETE_TEXT)
        else:
            self.delete_action.setText(_DELETE_CONFIRM_TEXT if self._marked else _DELETE_SELECT_TEXT)
        self.delete_action.setToolTip("Press again to cancel" if self._delete_mode and not self._marked else "")
        for card in self.board_view.cards():
            card.set_marked(card.task.id in self._marked)
            card.set_draggable(not self._delete_mode)
            if not self._delete_mode:
                card.setCursor(Qt.CursorShape.OpenHandCursor)
            elif card.task.stage == Stage.IN_PROCESS:
                card.setCursor(Qt.CursorShape.ForbiddenCursor)
            else:
                card.setCursor(Qt.CursorShape.CrossCursor)

    def _confirm_delete(self, count: int) -> bool:
        noun = "Task" if count == 1 else "Tasks"
        answer = QMessageBox.warning(
            self,
            "Delete Tasks",
            f"Are you sure you want to delete {count} {noun}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self._delete_mode:
            self._set_delete_mode(False)
            return
        super().keyPressEvent(event)

    # Context menus

    def card_menu(self, task_id: str) -> QMenu | None:
        """The right-click menu for a Task: Duplicate and Delete in Inbox, Delete in Done, none in In Process."""
        stage = self._board.task(task_id).stage
        if stage == Stage.IN_PROCESS or self._delete_mode:
            return None
        menu = QMenu(self)
        if stage == Stage.INBOX:
            menu.addAction("Duplicate Task", lambda: self._duplicate(task_id))
        menu.addAction("Delete Task", lambda: self._delete_one(task_id))
        return menu

    def _show_card_menu(self, task_id: str, at: QPoint) -> None:
        menu = self.card_menu(task_id)
        if menu is not None:
            menu.exec(at)

    def _duplicate(self, task_id: str) -> None:
        self._task_created(self._board.duplicate_task(task_id).id)

    def _delete_one(self, task_id: str) -> None:
        if self._confirm_delete(1):
            self._board.delete_task(task_id)
            self.refresh()

    def refresh(self) -> None:
        """Redraw the sidebar's Tags, the Board and the Notebook. A selected Tag that no Task or Note has any
        more is dropped."""
        self._show_tags()
        self.board_view.set_tag_filter(self._tag_filter)
        self.notebook_view.set_tag_filter(self._tag_filter)
        self._marked &= {t.id for stage in Stage for t in self._board.column(stage)}
        self._show_delete_mode()

    def _show_tags(self) -> None:
        """The sidebar lists every Tag in both views, each counted for the view on screen."""
        own = self._notebook.tags() if self.current_view() == "notebook" else self._board.tags()
        counts = {name.casefold(): count for name, count in own}
        tags = sorted(
            ((name, counts.get(name.casefold(), 0)) for name, _ in self._all_tags()),
            key=lambda item: item[0].casefold(),
        )
        self._tag_filter = self._tag_filter & {name.casefold() for name, _ in tags}
        self.sidebar.set_tags(tags, self._tag_filter)

    def toggle_tag(self, key: str) -> None:
        self._tag_filter = self._tag_filter ^ {key}
        self.refresh()

    def clear_tag_filter(self) -> None:
        self._tag_filter = frozenset()
        self.refresh()

    def _task_created(self, task_id: str) -> None:
        """Creating a Task clears the Tag filter, so the new Task is never hidden, and shows where it landed."""
        self.clear_tag_filter()
        self.board_view.highlight(task_id)

    def new_task(self) -> None:
        dialog = TaskDialog(self._board, parent=self, suggest_tags=self.suggest_tags)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._task_created(dialog.task_id)
        else:
            self.refresh()

    def open_task(self, task_id: str) -> None:
        """Edit a Task. If saving moves it, show where it went; if the Tag filter now hides it, clear the filter."""
        before = self._place(task_id)
        TaskDialog(self._board, self._board.task(task_id), parent=self, suggest_tags=self.suggest_tags).exec()
        if not self._board.has_task(task_id):  # deleted from the dialog
            self.refresh()
        elif self._tag_filter and not self._board.task(task_id).matches_tag_filter(self._tag_filter):
            self.clear_tag_filter()
            self.board_view.highlight(task_id)
        else:
            self.refresh()
            if self._place(task_id) != before:
                self.board_view.highlight(task_id)

    def _place(self, task_id: str) -> tuple[Stage, int]:
        """Where a Task sits: its Stage and its position in that Stage's Column."""
        stage = self._board.task(task_id).stage
        return stage, [t.id for t in self._board.column(stage)].index(task_id)

    def handle_drop(
        self, task_id: str, stage: Stage, kind: LaneKind | None, index: int, at: QPoint | None = None
    ) -> None:
        """Move a dropped Task; dropping onto the other kind of Lane converts it first.

        A Task the Board refuses to complete stays put, and a balloon at `at` says why. A Task that moved is
        highlighted where it landed.
        """
        task = self._board.task(task_id)
        moved = False
        if stage == Stage.DONE:
            try:
                self._board.move_task(task_id, stage)
                moved = True
            except UnfinishedSubtasks as refused:
                self.balloon.show_at(at or QCursor.pos(), str(refused))
        elif kind == task.kind:
            self._board.move_task(task_id, stage, priority=index + 1)
            moved = True
        elif kind == LaneKind.TIME_LIMITED:
            dialog = TaskDialog(self._board, task, parent=self, require_date=True, suggest_tags=self.suggest_tags)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._board.move_task(task_id, stage)
                moved = True
        else:
            answer = QMessageBox.question(
                self,
                "Make it a Someday Task?",
                f"Moving “{task.title}” to Someday clears its Due date and Deadline. Continue?",
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._board.edit_task(task_id, due_date=None, deadline=None)
                self._board.move_task(task_id, stage, priority=index + 1)
                moved = True
        self.refresh()
        if moved:
            self.board_view.highlight(task_id)
