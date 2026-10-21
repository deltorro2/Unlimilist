"""The Notebook: a table of every Note, with Quick note and the Notebook search above it. A search splits the table
in two: Exact matches above Partial matches. Choosing a Note opens it (Show Note) in place of the tables."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPoint, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from unlimilist.note_import import FILE_FILTER, ImportRefused, import_file
from unlimilist.note_search import MIN_CHARS, NoteSearch, SearchResult
from unlimilist.notebook import Note, Notebook
from unlimilist.notebook_password import NotebookPassword
from unlimilist.secure import WrongPassword
from unlimilist.ui import password_dialogs
from unlimilist.ui.icons import icon
from unlimilist.ui.note_page import NotePage, format_when
from unlimilist.ui.note_rows import select_row, style_rows
from unlimilist.ui.search_field import SearchField
from unlimilist.ui.toast import Toast

TITLE, CREATED, OPENED, TYPE, SIZE = range(5)
_HEADERS = ["Title", "Created", "Last opened", "Type", "Size"]
# A column's first click sorts the way you most likely want: names A to Z, the newest dates and biggest first.
_FIRST_ORDER = {
    TITLE: Qt.SortOrder.AscendingOrder,
    CREATED: Qt.SortOrder.DescendingOrder,
    OPENED: Qt.SortOrder.DescendingOrder,
    TYPE: Qt.SortOrder.AscendingOrder,
    SIZE: Qt.SortOrder.DescendingOrder,
}
_HIGHLIGHT = QColor("#FFE066")
_HIGHLIGHT_HOLD_MS = 1000  # as on the Board's cards
_HIGHLIGHT_FADE_MS = 400
_INK = QColor("#1B1B1F")  # the Title
_SOFT_INK = QColor("#5A5F6B")  # the other columns, so the Title stands out


def format_size(size: int) -> str:
    """"820 B", "14 KB", "1.2 MB"."""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{round(size / 1024)} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def _sort_key(note: Note, column: int):
    return {
        TITLE: lambda: note.title.casefold(),
        CREATED: lambda: note.created_at,
        OPENED: lambda: (note.opened_at is not None, note.opened_at or note.created_at),
        TYPE: lambda: note.secured,
        SIZE: lambda: note.size,
    }[column]()


class NotebookView(QWidget):
    noteCreated = Signal(str)
    notesChanged = Signal()  # a Note was saved, opened or deleted: its Tags or dates may have changed

    def __init__(
        self,
        notebook: Notebook,
        password: NotebookPassword,
        suggest_tags: Callable[[str], list[str]],
        parent=None,
        search: NoteSearch | None = None,
    ):
        super().__init__(parent)
        self._notebook = notebook
        self._password = password
        self._search = search or NoteSearch(notebook)
        self._search.set_secured_reader(self._read_secured)
        self._secured_searchable = False  # whether the search has read the Secured Notes since the unlock
        self._search_text: str | None = None  # the Notebook search applied with Enter
        self._toast: Toast | None = None
        self._tag_filter: frozenset[str] = frozenset()
        self._sort: tuple[int, Qt.SortOrder] | None = None  # None: the default order
        self._highlighted: str | None = None
        self._strength = 0.0  # how yellow the highlighted row is, 1 to 0
        self._pending_highlight: str | None = None  # shown once the table is back
        self._selected: str | None = None  # the Note shown last: drawn selected in the list
        self._fade = QVariantAnimation(self)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.setDuration(_HIGHLIGHT_FADE_MS)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.valueChanged.connect(self._paint_highlight)
        self._fade.finished.connect(self._highlight_done)
        self._hold = QTimer(self)
        self._hold.setSingleShot(True)
        self._hold.timeout.connect(self._fade.start)

        self.quick_add = QLineEdit()
        self.quick_add.setObjectName("quickAdd")
        self.quick_add.setPlaceholderText("＋ Quick note — type it, press Enter")
        self.quick_add.returnPressed.connect(self._quick_add)
        self.search_field = SearchField()
        self.search_field.setObjectName("noteSearch")
        self.search_field.setPlaceholderText("Search Notes")
        self.search_field.textChanged.connect(self._search_typed)
        self.search_field.returnPressed.connect(lambda: self.apply_search(self.search_field.text()))
        self.search_field.escapePressed.connect(self.clear_search)
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(self.quick_add, 7)  # Quick note keeps 70% of the line
        top.addWidget(self.search_field, 3)

        self.table = self._make_table()  # every Note, or a search's Exact matches
        self.partial_table = self._make_table()  # a search's Partial matches
        self.exact_label = QLabel("Exact matches")
        self.partial_label = QLabel("Partial matches")
        for label in (self.exact_label, self.partial_label):
            label.setObjectName("matchesHeader")

        self.empty_label = QLabel()
        self.empty_label.setObjectName("notesEmpty")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        table_page = QWidget()
        table_layout = QVBoxLayout(table_page)
        table_layout.setContentsMargins(12, 12, 12, 12)
        table_layout.setSpacing(10)
        table_layout.addLayout(top)
        table_layout.addWidget(self.exact_label)
        table_layout.addWidget(self.table, 1)
        table_layout.addWidget(self.partial_label)
        table_layout.addWidget(self.partial_table, 1)
        table_layout.addWidget(self.empty_label, 1)

        self.note_page = NotePage(notebook, password, suggest_tags)
        self.note_page.backClicked.connect(self.show_table)
        self.note_page.deleteClicked.connect(self._delete_shown)
        self.note_page.created.connect(self._created_on_page)
        self.note_page.saved.connect(lambda _: self.notesChanged.emit())

        self._pages = QStackedWidget()
        self._pages.addWidget(table_page)
        self._pages.addWidget(self.note_page)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._pages)
        self.refresh()

    def set_notebook(self, notebook: Notebook, search: NoteSearch | None = None) -> None:
        self._notebook = notebook
        self._search = search or NoteSearch(notebook)
        self._search.set_secured_reader(self._read_secured)
        self._secured_searchable = False
        self.note_page.set_notebook(notebook)
        self.refresh()

    def flush_search_index(self) -> None:
        self._search.flush()

    def _make_table(self) -> QTableWidget:
        table = QTableWidget(0, len(_HEADERS))
        table.setObjectName("notesTable")
        table.setHorizontalHeaderLabels(_HEADERS)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.verticalHeader().hide()
        style_rows(table)
        table.setCursor(Qt.CursorShape.PointingHandCursor)
        header = table.horizontalHeader()
        header.setSectionResizeMode(TITLE, QHeaderView.ResizeMode.Stretch)
        for column in (CREATED, OPENED, TYPE, SIZE):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(False)
        header.sectionClicked.connect(self.sort_by)
        table.cellClicked.connect(lambda row, column: self.open_note(_row_id(table, row)))
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(lambda at: self._show_menu(table, at))
        return table

    # The table

    def shown_ids(self) -> list[str]:
        """The ids of the Notes in the (top) table, top to bottom."""
        return [_row_id(self.table, row) for row in range(self.table.rowCount())]

    def partial_ids(self) -> list[str]:
        """The ids of a search's Partial matches, top to bottom."""
        return [_row_id(self.partial_table, row) for row in range(self.partial_table.rowCount())]

    def row_texts(self, note_id: str) -> list[str]:
        row = self.shown_ids().index(note_id)
        return [self.table.item(row, column).text() for column in range(len(_HEADERS))]

    def set_tag_filter(self, tag_filter: frozenset[str]) -> None:
        """Show only Notes with any of these Tags (case-folded keys); empty shows every Note."""
        self._tag_filter = tag_filter
        self.refresh()

    def sort_by(self, column: int) -> None:
        """Sort by a column; clicking it again turns the order around."""
        if self._sort and self._sort[0] == column:
            order = (
                Qt.SortOrder.DescendingOrder
                if self._sort[1] == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            order = _FIRST_ORDER[column]
        self._sort = (column, order)
        for table in (self.table, self.partial_table):
            header = table.horizontalHeader()
            header.setSortIndicatorShown(True)
            header.setSortIndicator(column, order)
        self.refresh()

    def refresh(self) -> None:
        notes = [n for n in self._notebook.notes() if n.matches_tag_filter(self._tag_filter)]
        if self._sort:
            column, order = self._sort
            notes.sort(key=lambda n: _sort_key(n, column), reverse=order == Qt.SortOrder.DescendingOrder)
        partial: list[Note] = []
        searching = self._search_text is not None
        if searching:
            result = self._run_search(self._search_text)
            exact = set(result.exact)
            # Most of the words first; the table's order within the same number.
            partial = sorted((n for n in notes if n.id in result.word_counts), key=lambda n: -result.word_counts[n.id])
            notes = [n for n in notes if n.id in exact]
        _fill(self.table, notes)
        _fill(self.partial_table, partial)
        for table, listed in ((self.table, notes), (self.partial_table, partial)):
            ids = [n.id for n in listed]
            select_row(table, ids.index(self._selected) if self._selected in ids else -1)
        if self._highlighted is not None:  # still yellow if it is still listed
            if self._highlighted in self.shown_ids():
                self._paint_highlight(self._strength)
            else:
                self._stop_highlight()
        self.table.setVisible(bool(notes))
        self.exact_label.setVisible(searching and bool(notes))
        self.partial_table.setVisible(bool(partial))
        self.partial_label.setVisible(bool(partial))
        empty = not notes and not partial
        self.empty_label.setVisible(empty)
        if not empty:
            return
        if searching:
            self.empty_label.setText(f"No Notes match “{self._search_text.strip()}”.")
        elif self._notebook.notes():
            self.empty_label.setText("No Notes have the selected Tags.")
        else:
            self.empty_label.setText("No Notes yet. Write one above, press ＋ New Note, or Import…")

    def _quick_add(self) -> None:
        note = self._notebook.quick_add(self.quick_add.text())
        if note is None:
            return
        self.quick_add.clear()
        self.clear_search()
        self.noteCreated.emit(note.id)
        self.refresh()
        self.highlight(note.id)

    # The Notebook search

    def is_searching(self) -> bool:
        return self._search_text is not None

    def find(self) -> None:
        """⌘F: the search field over the table, or Find in Note on a shown Note (starting with the search text)."""
        if self.is_showing_note():
            self.note_page.open_find(self._search_text)
        else:
            self.search_field.setFocus()
            self.search_field.selectAll()

    def apply_search(self, text: str) -> None:
        """Enter: list the Exact and Partial matches. With Partial matches only, a "Partial match" toast says so."""
        self._dismiss_toast()
        if len(text.strip()) < MIN_CHARS:
            self.clear_search()
            return
        self._search_text = text
        self.refresh()
        result = self._run_search(text)
        if not result.whole_found and result.found_words:
            self.toast().show_message("Partial match")

    def clear_search(self) -> None:
        if self.search_field.text():
            self.search_field.blockSignals(True)
            self.search_field.clear()
            self.search_field.blockSignals(False)
        self.search_field.set_green([])
        if self._search_text is not None:
            self._search_text = None
            self.refresh()

    def _dismiss_toast(self) -> None:
        if self._toast is not None:
            self._toast.dismiss()

    def toast(self) -> Toast:
        if self._toast is None:
            self._toast = Toast(self.window())
        return self._toast

    def _search_typed(self, text: str) -> None:
        """Colour what is found as it is typed: all of it, or else the words found. An emptied field (its ✕)
        ends the search."""
        if not text:
            self.clear_search()
            return
        result = self._run_search(text)
        if result.whole_found:
            start = len(text) - len(text.lstrip())
            self.search_field.set_green([(start, len(text.strip()))])
        else:
            self.search_field.set_green(_word_ranges(text, result.found_words))

    def _run_search(self, text: str) -> SearchResult:
        if self._password.is_unlocked() and not self._secured_searchable:
            self._search.forget_secured()  # their Bodies can be read now
            self._secured_searchable = True
        return self._search.search(text)

    def _read_secured(self, note: Note) -> str | None:
        if not self._password.is_unlocked():
            return None
        try:
            return self._notebook.read_body(note.id, self._password.current())
        except WrongPassword:
            return None

    # Highlighting a new Note's row: yellow, a hold, then a quick fade, as on the Board

    def highlight(self, note_id: str) -> None:
        if not self.is_showing_table():
            self._pending_highlight = note_id
            return
        self._stop_highlight()
        if note_id not in self.shown_ids():
            return
        self._highlighted = note_id
        self._paint_highlight(1.0)
        self.table.scrollToItem(self.table.item(self.shown_ids().index(note_id), TITLE))
        self._hold.start(_HIGHLIGHT_HOLD_MS)

    def selected_id(self) -> str | None:
        return self._selected

    def is_highlighted(self, note_id: str) -> bool:
        return self._highlighted == note_id

    def _paint_highlight(self, strength) -> None:
        self._strength = float(strength)
        if self._highlighted not in self.shown_ids():
            return
        row = self.shown_ids().index(self._highlighted)
        colour = QColor(_HIGHLIGHT)
        colour.setAlphaF(float(strength))
        for column in range(len(_HEADERS)):
            self.table.item(row, column).setBackground(QBrush(colour))

    def _stop_highlight(self) -> None:
        self._hold.stop()
        self._fade.stop()
        if self._highlighted is not None:
            self._paint_highlight(0.0)
            self._highlighted = None

    def _highlight_done(self) -> None:
        self._paint_highlight(0.0)
        self._highlighted = None

    # Show Note

    def is_showing_table(self) -> bool:
        return self._pages.currentIndex() == 0

    def is_showing_note(self) -> bool:
        return self._pages.currentWidget() is self.note_page

    def open_note(self, note_id: str) -> bool:
        """Show a Note in View mode. A Secured Note needs the Notebook password, once a session."""
        note = self._notebook.note(note_id)
        if note.secured and not self._password.is_unlocked():
            opens = lambda typed: self._opens(note_id, typed)  # noqa: E731
            if password_dialogs.ask_password(self, lambda typed: self._password.unlock(typed, opens)) is None:
                return False
        try:
            body = self._notebook.read_body(note_id, self._password.current())
        except WrongPassword:
            QMessageBox.warning(
                self, "Secured Note", f"“{note.title}” doesn't open with the Notebook password."
            )
            return False
        self._dismiss_toast()
        note = self._notebook.mark_opened(note_id)
        self.note_page.show_note(note, body)
        self._pages.setCurrentWidget(self.note_page)
        self.notesChanged.emit()
        return True

    def new_note(self) -> None:
        self.leave_note()
        self.note_page.start_new()
        self._pages.setCurrentWidget(self.note_page)

    def show_table(self) -> None:
        """Back to the list as it was (search, Tags, sort), saving the Note on the page. That Note is drawn
        selected and scrolled into view."""
        shown = self.note_page.note_id() if self.is_showing_note() else None
        self.leave_note()
        if shown is not None and self._notebook.has_note(shown):
            self._selected = shown
        self._pages.setCurrentIndex(0)
        self.refresh()
        self._scroll_to_selected()
        if self._pending_highlight:
            note_id, self._pending_highlight = self._pending_highlight, None
            self.highlight(note_id)

    def _scroll_to_selected(self) -> None:
        for table, ids in ((self.table, self.shown_ids()), (self.partial_table, self.partial_ids())):
            if self._selected in ids:
                table.scrollToItem(table.item(ids.index(self._selected), TITLE))

    def leave_note(self) -> None:
        """Save and close the Note on the page, if any (the table stays where it is)."""
        if self.note_page.has_note():
            self.note_page.close_note()
            self.notesChanged.emit()

    def save_now(self) -> None:
        """Save the Note on the page, if it has edits, and keep it open (e.g. as the app quits)."""
        self.note_page.save()

    def _opens(self, note_id: str, typed: str) -> bool:
        try:
            self._notebook.read_body(note_id, typed)
        except WrongPassword:
            return False
        return True

    def _created_on_page(self, note_id: str) -> None:
        self.clear_search()
        self._pending_highlight = note_id
        self.noteCreated.emit(note_id)

    # Deleting

    def note_menu(self, note_id: str) -> QMenu:
        menu = QMenu(self)
        menu.addAction("Delete Note", lambda: self.delete_note(note_id))
        return menu

    def _show_menu(self, table: QTableWidget, at: QPoint) -> None:
        item = table.itemAt(at)
        if item is not None:
            self.note_menu(item.data(Qt.ItemDataRole.UserRole)).exec(table.viewport().mapToGlobal(at))

    def delete_note(self, note_id: str) -> bool:
        """Delete after asking. A Secured Note needs the Notebook password, and its file is removed for good."""
        note = self._notebook.note(note_id)
        if note.secured:
            typed = password_dialogs.ask_password(
                self,
                self._password.check,
                title="Delete Secured Note",
                message=f"Type the Notebook password to delete “{note.title}”. It can't be recovered.",
            )
            if typed is None:
                return False
        else:
            answer = QMessageBox.warning(
                self,
                "Delete Note",
                f"Are you sure you want to delete “{note.title}”?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
        if self.note_page.note_id() == note_id:
            self.note_page.close_note()  # its edits are saved first, then the file goes
            self._pages.setCurrentIndex(0)
        self._notebook.delete(note_id)
        self.refresh()
        self.notesChanged.emit()
        return True

    def _delete_shown(self) -> None:
        note_id = self.note_page.note_id()
        if note_id is not None:
            self.delete_note(note_id)
            return
        # A new Note not saved yet: dropped without asking.
        self.note_page.start_new()  # emptied, so closing it saves nothing
        self.note_page.close_note()
        self._pages.setCurrentIndex(0)
        self.refresh()

    # Importing

    def import_notes(self) -> None:
        """From the table, each file becomes a Note. With a Note open, the files' text goes into its Body: at
        the cursor if the Body editor has the focus, else at the end. Decided before the file dialog takes it."""
        into_note = self.is_showing_note()
        at_cursor = into_note and self.note_page.is_editing() and self.note_page.editor.hasFocus()
        paths, _ = QFileDialog.getOpenFileNames(self, "Import into the Notebook", str(Path.home()), FILE_FILTER)
        if not paths:
            return
        if into_note:
            self.import_into_note([Path(p) for p in paths], at_cursor)
        else:
            self.import_paths([Path(p) for p in paths])

    def import_paths(self, paths: list[Path]) -> list[str]:
        """One Open Note per file; returns the ids made. Files that can't be imported are listed in a message."""
        converted = self._convert(paths)
        made = [self._notebook.create(title, markdown).id for title, markdown in converted]
        if made:
            self.leave_note()
            self.clear_search()
            self._pages.setCurrentIndex(0)
            self.noteCreated.emit(made[-1])
            self.refresh()
            self.highlight(made[-1])
        return made

    def import_into_note(self, paths: list[Path], at_cursor: bool) -> None:
        """Add the files' text, one after another, to the Body of the Note on the page; it stays in Edit mode."""
        texts = [markdown for _, markdown in self._convert(paths) if markdown]
        if texts:
            self.note_page.insert_markdown("\n\n".join(texts), at_cursor)

    def _convert(self, paths: list[Path]) -> list[tuple[str, str]]:
        """(Title, Markdown) for each file that can be imported; the others are listed in a message."""
        converted, refused = [], []
        for path in paths:
            try:
                converted.append(import_file(path))
            except ImportRefused as reason:
                refused.append(str(reason))
            except OSError as error:
                refused.append(f"{path.name} could not be read: {error.strerror}")
        if refused:
            QMessageBox.warning(self, "Import", "Some files were not imported:\n\n" + "\n".join(refused))
        return converted


def _row_id(table: QTableWidget, row: int) -> str:
    return table.item(row, TITLE).data(Qt.ItemDataRole.UserRole)


def _fill(table: QTableWidget, notes: list[Note]) -> None:
    table.setRowCount(len(notes))
    for row, note in enumerate(notes):
        cells = [note.title, format_when(note.created_at), format_when(note.opened_at), "", format_size(note.size)]
        for column, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, note.id)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            table.setItem(row, column, item)
        title = table.item(row, TITLE)
        title.setToolTip(note.title)
        bold = QFont(title.font())
        bold.setBold(True)  # every Title, whatever the Note's state
        title.setFont(bold)
        title.setForeground(_INK)
        for column in (CREATED, OPENED, SIZE):
            table.item(row, column).setForeground(_SOFT_INK)
        type_item = table.item(row, TYPE)
        type_item.setIcon(icon("lock" if note.secured else "lock-open", "#3A3D45" if note.secured else "#9095A0"))
        type_item.setToolTip("Secured" if note.secured else "Open")
        type_item.setData(Qt.ItemDataRole.AccessibleTextRole, "Secured" if note.secured else "Open")


def _word_ranges(text: str, words: tuple[str, ...]) -> list[tuple[int, int]]:
    """(start, length) of each place in `text` where one of `words` is written, ignoring case."""
    folded = text.casefold()
    ranges = []
    for word in words:
        start = folded.find(word)
        while start != -1:
            ranges.append((start, len(word)))
            start = folded.find(word, start + len(word))
    return sorted(ranges)
