"""Show Note: one Note in place of the Notebook's table.

Three header lines (Back, Title, Type, Delete and the View/Edit switch; the dates; the Tags), then the Body.
View mode renders the Markdown; Edit mode edits the Title, Type, Tags and the raw Markdown. Edits are saved on
leaving Edit mode, on leaving the Note, and every five minutes while Edit mode stays on.
"""

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import QEvent, QObject, QSize, QStringListModel, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QKeySequence,
    QShortcut,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QPushButton,
    QTextEdit,
    QComboBox,
    QCompleter,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from unlimilist.notebook import Note, Notebook, NoteType, is_tag_name
from unlimilist.notebook_password import NotebookPassword
from unlimilist.ui import password_dialogs
from unlimilist.ui.flow_layout import FlowLayout
from unlimilist.ui.icons import icon
from unlimilist.ui.markdown_highlighter import MarkdownHighlighter
from unlimilist.ui.note_viewer import NoteViewer

AUTOSAVE_MS = 5 * 60 * 1000
_TYPES = [(NoteType.OPEN, "Open", "lock-open"), (NoteType.SECURED, "Secured", "lock")]
_GAP = " · "

CHEAT_SHEET = """
<table cellspacing="0" cellpadding="3">
<tr><td><b>Write</b></td><td><b>To get</b></td></tr>
<tr><td><code># Title</code> &nbsp; <code>## Section</code></td><td>Headings</td></tr>
<tr><td><code>**bold**</code> &nbsp; <code>*italic*</code> &nbsp; <code>~~strike~~</code></td>
<td><b>bold</b>, <i>italic</i>, <s>strike</s></td></tr>
<tr><td><code>`code`</code></td><td>Code in a line</td></tr>
<tr><td><code>```</code> … <code>```</code></td><td>A block of code</td></tr>
<tr><td><code>- item</code> &nbsp; <code>1. item</code></td><td>Bulleted and numbered lists</td></tr>
<tr><td><code>- [ ] to do</code> &nbsp; <code>- [x] done</code></td><td>Checkboxes</td></tr>
<tr><td><code>[text](https://…)</code></td><td>A link</td></tr>
<tr><td><code>&gt; quote</code></td><td>A quote</td></tr>
<tr><td><code>---</code></td><td>A line across</td></tr>
<tr><td><code>| A | B |</code><br><code>| --- | --- |</code><br><code>| 1 | 2 |</code></td><td>A table</td></tr>
<tr><td><code>```mermaid</code><br><code>flowchart LR</code><br><code>&nbsp;&nbsp;A --&gt; B</code><br><code>```</code></td>
<td>A diagram (Mermaid), drawn in View mode.<br>Close it with <code>```</code> on a line of its own.</td></tr>
<tr><td>an empty line</td><td>A new paragraph</td></tr>
</table>
"""


def _gap(text: str, leading: bool) -> str:
    """The newlines that leave a blank line between `text` (what comes before or after an insert) and the
    inserted text. None at the very start or end of the Body."""
    if not text:
        return ""
    edge = text[len(text.rstrip("\n")) :] if leading else text[: len(text) - len(text.lstrip("\n"))]
    return "\n" * max(0, 2 - len(edge))


def format_when(when: datetime | None) -> str:
    """"21 Oct 2026, 14:05", or "—" for never."""
    return f"{when.day} {when:%b %Y, %H:%M}" if when else "—"


class CheatSheet(QFrame):
    """The most used Markdown, in a big tooltip-like popup. Any key or click closes it."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("cheatSheet")
        label = QLabel(CHEAT_SHEET)
        label.setTextFormat(Qt.TextFormat.RichText)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(label)

    def show_above(self, anchor: QWidget) -> None:
        self.adjustSize()
        corner = anchor.mapToGlobal(anchor.rect().topRight())
        self.move(corner.x() - self.width(), corner.y() - self.height() - 6)
        self.show()

    def keyPressEvent(self, event):
        self.close()

    def mousePressEvent(self, event):
        self.close()


_FOUND = QColor("#FFE066")  # a found place's background, the yellow of a new card


class FindBar(QFrame):
    """Find in Note: a small bar floating at the top-right of the Body, with the text to find, Next and Cancel."""

    nextClicked = Signal()
    closeClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("findBar")
        self.field = QLineEdit()
        self.field.setObjectName("findField")
        self.field.setPlaceholderText("Find in Note")
        self.field.setMinimumWidth(200)
        self.field.returnPressed.connect(self.nextClicked)
        self.next_button = QPushButton("Next")
        self.next_button.setObjectName("findNext")
        self.next_button.clicked.connect(self.nextClicked)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("findCancel")
        self.cancel_button.clicked.connect(self.closeClicked)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)
        layout.addWidget(self.field)
        layout.addWidget(self.next_button)
        layout.addWidget(self.cancel_button)
        self.hide()

    def set_not_found(self, not_found: bool) -> None:
        self.field.setProperty("notFound", not_found)
        self.field.style().polish(self.field)


class _TagBubble(QFrame):
    removeClicked = Signal(str)

    def __init__(self, name: str, removable: bool, parent=None):
        super().__init__(parent)
        self.name = name
        self.setObjectName("noteTag")
        label = QLabel(f"#{name}")
        label.setObjectName("noteTagText")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 1, 4 if removable else 8, 1)
        layout.setSpacing(2)
        layout.addWidget(label)
        self.remove_button = None
        if removable:
            self.remove_button = QToolButton()
            self.remove_button.setObjectName("noteTagRemove")
            self.remove_button.setText("✕")
            self.remove_button.setToolTip(f"Remove #{name}")
            self.remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.remove_button.clicked.connect(lambda: self.removeClicked.emit(self.name))
            layout.addWidget(self.remove_button)


class TagArea(QWidget):
    """A Note's Tags: bubbles, and in Edit mode a "+ tag…" field that suggests existing Tags as you type.
    Enter adds the highlighted suggestion, or the typed Tag if nothing is suggested."""

    changed = Signal()

    def __init__(self, suggest: Callable[[str], list[str]], parent=None):
        super().__init__(parent)
        self._suggest = suggest
        self._tags: list[str] = []
        self._editable = False
        self._flow = FlowLayout(self)
        self._flow.setContentsMargins(0, 0, 0, 0)
        heading = QLabel("TAGS")
        heading.setObjectName("noteTagsHeader")
        self._flow.addWidget(heading)
        self._bubbles: list[_TagBubble] = []

        self.field = QLineEdit()
        self.field.setObjectName("noteTagField")
        self.field.setPlaceholderText("+ tag…")
        self.field.setFixedWidth(140)
        self._model = QStringListModel(self)
        self.completer = QCompleter(self._model, self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.popup().setObjectName("tagPopup")
        self.completer.setWidget(self.field)
        self.completer.activated.connect(self._suggestion_chosen)
        self.field.textEdited.connect(self._typed)
        self.field.returnPressed.connect(self._enter)
        self._flow.addWidget(self.field)
        self.set_editable(False)

    def tags(self) -> tuple[str, ...]:
        return tuple(self._tags)

    def set_tags(self, tags) -> None:
        self._tags = list(tags)
        self._redraw()

    def set_editable(self, editable: bool) -> None:
        self._editable = editable
        self.field.setVisible(editable)
        if not editable:
            self.field.clear()
            self.completer.popup().hide()
        self._redraw()

    def add_tag(self, name: str) -> bool:
        name = name.strip().lstrip("#").rstrip("-")
        if not is_tag_name(name):
            self.field.setProperty("invalid", bool(name))
            self.field.setToolTip("A Tag is one word: letters, digits, - and _, starting with a letter")
            self.field.style().polish(self.field)
            return False
        self.field.setProperty("invalid", False)
        self.field.setToolTip("")
        self.field.style().polish(self.field)
        if name.casefold() not in {t.casefold() for t in self._tags}:
            self._tags.append(name)
            self._redraw()
            self.changed.emit()
        return True

    def remove_tag(self, name: str) -> None:
        self._tags = [t for t in self._tags if t.casefold() != name.casefold()]
        self._redraw()
        self.changed.emit()

    def bubbles(self) -> list[_TagBubble]:
        return list(self._bubbles)

    def suggestions(self) -> list[str]:
        return self._model.stringList()

    def _typed(self, text: str) -> None:
        typed = text.strip().lstrip("#")
        present = {t.casefold() for t in self._tags}
        names = [n for n in self._suggest(typed) if n.casefold() not in present] if typed else []
        self._model.setStringList(names)
        if names:
            self.completer.complete()
            self.completer.popup().setCurrentIndex(self.completer.completionModel().index(0, 0))
        else:
            self.completer.popup().hide()

    def _enter(self) -> None:
        popup = self.completer.popup()
        if popup.isVisible() and popup.currentIndex().isValid():
            self._suggestion_chosen(popup.currentIndex().data())
            return
        if self.add_tag(self.field.text()):
            self.field.clear()

    def _suggestion_chosen(self, name: str) -> None:
        self.completer.popup().hide()
        self.add_tag(name)
        QTimer.singleShot(0, self.field.clear)  # after QCompleter has written the choice into the field
        self._model.setStringList([])

    def _redraw(self) -> None:
        for bubble in self._bubbles:
            self._flow.removeWidget(bubble)
            bubble.hide()
            bubble.setParent(None)
            bubble.deleteLater()
        self._bubbles = []
        self._flow.removeWidget(self.field)
        for name in self._tags:
            bubble = _TagBubble(name, self._editable)
            bubble.removeClicked.connect(self.remove_tag)
            self._flow.addWidget(bubble)
            self._bubbles.append(bubble)
        self._flow.addWidget(self.field)  # always last
        self.updateGeometry()


class NotePage(QWidget):
    backClicked = Signal()
    deleteClicked = Signal()
    created = Signal(str)  # a new Note was saved for the first time
    saved = Signal(str)

    def __init__(
        self,
        notebook: Notebook,
        password: NotebookPassword,
        suggest_tags: Callable[[str], list[str]],
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("notePage")
        self._notebook = notebook
        self._password = password
        self._note_id: str | None = None
        self._open = False  # whether a Note (new or saved) is on the page
        self._saved: tuple | None = None  # what was last saved, to tell whether there is anything to save
        self._editing = False

        # Line 1: Back, the Title, Type, Delete and the View/Edit switch.
        self.back_button = QToolButton()
        self.back_button.setObjectName("noteBack")
        self.back_button.setIcon(icon("arrow-left", "#2F6FED", 16))
        self.back_button.setText("Notebook")
        self.back_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.clicked.connect(self.backClicked)
        self.lock_label = QLabel()
        self.lock_label.setPixmap(icon("lock", "#6B7080", 16).pixmap(16, 16))
        self.lock_label.setToolTip("Secured Note")
        self.title_edit = QLineEdit()
        self.title_edit.setObjectName("noteTitle")
        self.title_edit.setPlaceholderText("Title")
        self.type_box = QComboBox()
        self.type_box.setObjectName("noteType")
        self.type_box.setToolTip("Type: a Secured Note's Body is encrypted with the Notebook password")
        for note_type, label, icon_name in _TYPES:
            self.type_box.addItem(icon(icon_name, "#3A3D45", 16), label, note_type)
        self.type_box.activated.connect(self._type_chosen)
        self.delete_button = QToolButton()
        self.delete_button.setObjectName("noteDelete")
        self.delete_button.setIcon(icon("trash", "#7A7F8C", 18, hover_colour="#E53935"))
        self.delete_button.setIconSize(QSize(18, 18))
        self.delete_button.setToolTip("Delete Note")
        self.delete_button.clicked.connect(self.deleteClicked)
        self.view_button = QToolButton()
        self.edit_button = QToolButton()
        switch = QFrame()
        switch.setObjectName("modeSwitch")
        switch_layout = QHBoxLayout(switch)
        switch_layout.setContentsMargins(2, 2, 2, 2)
        switch_layout.setSpacing(0)
        self._modes = QButtonGroup(self)
        for button, text in [(self.view_button, "View"), (self.edit_button, "Edit")]:
            button.setObjectName("modeButton")
            button.setText(text)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._modes.addButton(button)
            switch_layout.addWidget(button)
        self.view_button.setChecked(True)
        self.edit_button.toggled.connect(self.set_editing)
        line1 = QHBoxLayout()
        line1.setSpacing(8)
        line1.addWidget(self.back_button)
        line1.addWidget(self.lock_label)
        line1.addWidget(self.title_edit, 1)
        line1.addWidget(self.type_box)
        line1.addWidget(self.delete_button)
        line1.addWidget(switch)

        # Line 2: the dates. Line 3: the Tags.
        self.dates_label = QLabel()
        self.dates_label.setObjectName("noteDates")
        self.tag_area = TagArea(suggest_tags)

        # The Body: raw Markdown to edit, or rendered to read.
        self.editor = QPlainTextEdit()
        self.editor.setObjectName("noteEditor")
        self.editor.setPlaceholderText("Write in Markdown…")
        self._highlighter = MarkdownHighlighter(self.editor.document())
        # The web viewer is made the first time a Note is viewed: the web engine is slow to start.
        self._viewer: NoteViewer | None = None
        self._view_match: tuple[int, int] | None = None  # Find in View mode: (active match, how many)
        self.body = QStackedWidget()
        self.body.addWidget(QWidget())  # stands in for the viewer until it is made
        self.body.addWidget(self.editor)

        # Under the editor: the ⓘ that opens the Markdown cheat sheet.
        self.info_button = QToolButton()
        self.info_button.setObjectName("cheatSheetButton")
        self.info_button.setIcon(icon("info", "#6B7080", 16, hover_colour="#2F6FED"))
        self.info_button.setToolTip("Markdown cheat sheet")
        self.info_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.info_button.clicked.connect(self.show_cheat_sheet)
        self.cheat_sheet: CheatSheet | None = None
        hint = QLabel("Markdown")
        hint.setObjectName("noteFooterHint")
        self.footer = QFrame()
        self.footer.setObjectName("noteFooter")
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(10, 2, 6, 2)
        footer_layout.addWidget(hint)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.info_button)

        body_box = self.body_box = QFrame()
        body_box.setObjectName("noteBody")
        body_layout = QVBoxLayout(body_box)
        body_layout.setContentsMargins(1, 1, 1, 1)
        body_layout.setSpacing(0)
        body_layout.addWidget(self.body, 1)
        body_layout.addWidget(self.footer)

        # The three header lines. Over the main window, they sit right of the sidebar's view items (see set_corner).
        self.header = QWidget()
        self._header_layout = QVBoxLayout(self.header)
        self._header_layout.setContentsMargins(0, 0, 0, 0)
        self._header_layout.setSpacing(6)
        self._header_layout.addLayout(line1)
        self._header_layout.addWidget(self.dates_label)
        self._header_layout.addWidget(self.tag_area)

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)  # opaque, as it lies over the sidebar
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)
        layout.addWidget(self.header)
        layout.addSpacing(4)
        layout.addWidget(body_box, 1)

        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(AUTOSAVE_MS)
        self.autosave_timer.timeout.connect(self.save)

        # Find in Note, floating over the Body's top-right corner.
        self.find_bar = FindBar(body_box)
        self.find_bar.nextClicked.connect(self.find_next)
        self.find_bar.closeClicked.connect(self.close_find)
        self.find_bar.field.textEdited.connect(lambda _: self._restart_find())
        body_box.installEventFilter(self)
        self._found: tuple[int, int] | None = None  # (start, end) of the place found last
        # Esc closes the Find bar if it is open, else goes back to the list (saving, like Back).
        escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        escape.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        escape.activated.connect(self._escape)
        self._show_mode()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.body_box and event.type() == QEvent.Type.Resize:
            self._place_find_bar()
        return super().eventFilter(watched, event)

    def set_notebook(self, notebook: Notebook) -> None:
        self._notebook = notebook

    @property
    def viewer(self) -> NoteViewer:
        if self._viewer is None:
            self._viewer = NoteViewer()
            self._viewer.findDone.connect(self._view_found)
            placeholder = self.body.widget(0)
            self.body.insertWidget(0, self._viewer)
            self.body.removeWidget(placeholder)
            placeholder.deleteLater()
        return self._viewer

    def set_corner(self, width: int, height: int) -> None:
        """Leave the top-left `width` x `height` to the sidebar's view items: the header lines start right of
        them, and the Body below them, across the full width."""
        self._header_layout.setContentsMargins(width, 0, 0, 0)
        self.header.setMinimumHeight(max(0, height - self.layout().contentsMargins().top()))

    def note_id(self) -> str | None:
        return self._note_id

    def has_note(self) -> bool:
        return self._open

    def is_editing(self) -> bool:
        return self._editing

    def note_type(self) -> NoteType:
        return self.type_box.currentData()

    def show_note(self, note: Note, body: str) -> None:
        """Show a saved Note in View mode; `body` is its plain Body (a Secured Note's already decrypted)."""
        self._note_id = note.id
        self._open = True
        self._fill(note.title, body, note.tags, note.note_type)
        self._show_dates(note)
        self._saved = self._current()
        self._set_mode(False)

    def start_new(self) -> None:
        """An empty Note in Edit mode, the cursor in the Title. It is kept once it has a Title or a Body."""
        self._note_id = None
        self._open = True
        self._fill("", "", (), NoteType.OPEN)
        self.dates_label.setText("New Note")
        self._saved = self._current()
        self._set_mode(True)
        self.title_edit.setFocus()

    def set_editing(self, editing: bool) -> None:
        """Switch View/Edit; leaving Edit mode saves."""
        if editing != self._editing:
            self._set_mode(editing)

    def save(self) -> bool:
        """Save the edits, if there are any. A new Note with neither Title nor Body is not kept."""
        if not self._open:
            return False
        current = self._current()
        if current == self._saved:
            return False
        title, body, tags, note_type = current
        password = self._password.current() if note_type == NoteType.SECURED else None
        if self._note_id is None:
            note = self._notebook.create(title, body, tags, note_type, password, opened=True)
            if note is None:
                return False
            self._note_id = note.id
            self.created.emit(note.id)
        else:
            note = self._notebook.save(self._note_id, title, body, tags, note_type, password)
        # A Note saved without a Title became a Daily note: show the Title and Tag it got.
        if note.title != title:
            self.title_edit.setText(note.title)
        if note.tags != tags:
            self.tag_area.set_tags(note.tags)
        self._show_dates(note)
        self._saved = self._current()
        self.saved.emit(note.id)
        return True

    def close_note(self) -> None:
        """Save, then leave the page empty."""
        self.close_find()
        self.save()
        self.autosave_timer.stop()
        self._open = False
        self._note_id = None
        self._saved = None
        self._fill("", "", (), NoteType.OPEN)

    def insert_markdown(self, text: str, at_cursor: bool) -> None:
        """Add `text` to the Body, in Edit mode: at the cursor, or else at the end. A blank line keeps it apart
        from the text before and after it."""
        self.set_editing(True)
        cursor = self.editor.textCursor()
        if not at_cursor:
            cursor.movePosition(QTextCursor.MoveOperation.End)
        body = self.editor.toPlainText()
        before, after = body[: cursor.position()], body[cursor.position() :]
        cursor.beginEditBlock()  # one step to undo
        cursor.insertText(_gap(before, leading=True) + text)
        end = cursor.position()
        cursor.insertText(_gap(after, leading=False))
        cursor.endEditBlock()
        cursor.setPosition(end)
        self.editor.setTextCursor(cursor)
        self.editor.ensureCursorVisible()
        self.editor.setFocus()

    # Find in Note

    def open_find(self, text: str | None = None) -> None:
        """Show the Find bar, starting with `text` if given, ready to type."""
        if text:
            self.find_bar.field.setText(text)
            self._restart_find()
        self._place_find_bar()
        self.find_bar.show()
        self.find_bar.raise_()
        self.find_bar.field.setFocus()
        self.find_bar.field.selectAll()

    def is_finding(self) -> bool:
        return self.find_bar.isVisible()

    def found(self) -> tuple[int, int] | None:
        """Edit mode: (start, end) of the place found last in the Markdown."""
        return self._found

    def view_match(self) -> tuple[int, int] | None:
        """View mode: (which match, how many) of the place found last; None before an answer or if none."""
        return self._view_match

    def find_next(self) -> bool:
        """Select the next place holding the text, after the last one found; after the last, start at the top.
        In View mode the web engine answers a moment later (view_match)."""
        text = self.find_bar.field.text()
        if not text:
            return False
        if not self._editing:
            self.viewer.find(text)
            return True
        document = self.editor.document()
        start = self._found[1] if self._found else 0
        cursor = document.find(text, start)
        if cursor.isNull():
            cursor = document.find(text, 0)
        self.find_bar.set_not_found(cursor.isNull())
        if cursor.isNull():
            self._mark_found(None)
            return False
        self._mark_found(cursor)
        return True

    def close_find(self) -> None:
        if not self.find_bar.isVisible():
            return
        self.find_bar.hide()
        self._restart_find()
        (self.editor if self._editing else self.viewer).setFocus()

    def _escape(self) -> None:
        if self.is_finding():
            self.close_find()
        else:
            self.backClicked.emit()

    def _view_found(self, active: int, count: int) -> None:
        self._view_match = (active, count) if count else None
        self.find_bar.set_not_found(not count)

    def _restart_find(self) -> None:
        self.find_bar.set_not_found(False)
        self._mark_found(None)
        self._view_match = None
        if self._viewer is not None:
            self._viewer.clear_find()

    def _mark_found(self, cursor: QTextCursor | None) -> None:
        """Give the found place in the Markdown a yellow background and scroll to it; None clears the mark."""
        self.editor.setExtraSelections([])
        if cursor is None:
            self._found = None
            return
        self._found = (cursor.selectionStart(), cursor.selectionEnd())
        target = self.editor
        mark = QTextEdit.ExtraSelection()
        mark.cursor = cursor
        mark.format.setBackground(_FOUND)
        target.setExtraSelections([mark])
        caret = QTextCursor(cursor)
        caret.clearSelection()  # the caret goes after the place, so scrolling shows it but nothing is selected
        target.setTextCursor(caret)
        target.ensureCursorVisible()

    def _place_find_bar(self) -> None:
        self.find_bar.adjustSize()
        self.find_bar.move(self.body_box.width() - self.find_bar.width() - 10, 10)

    def show_cheat_sheet(self) -> None:
        self.cheat_sheet = CheatSheet(self)
        self.cheat_sheet.show_above(self.info_button)

    def _current(self) -> tuple:
        return (self.title_edit.text().strip(), self.editor.toPlainText(), self.tag_area.tags(), self.note_type())

    def _fill(self, title: str, body: str, tags, note_type: NoteType) -> None:
        self.title_edit.setText(title)
        self.editor.setPlainText(body)
        self.tag_area.set_tags(tags)
        self.type_box.setCurrentIndex(self.type_box.findData(note_type))
        self._render()

    def _show_dates(self, note: Note) -> None:
        self.dates_label.setText(
            f"Created {format_when(note.created_at)}{_GAP}Last opened {format_when(note.opened_at)}"
        )

    def _set_mode(self, editing: bool) -> None:
        if self._editing and not editing:
            self.save()
        self._restart_find()  # the other mode shows other text: start again from the top
        self._editing = editing
        if editing:
            self.autosave_timer.start()
        else:
            self.autosave_timer.stop()
            self._render()
        self._show_mode()
        # The focus goes into the Note, so its keys (Esc, ⌘F) work at once.
        if editing:
            self.editor.setFocus()
        elif self._open:
            self.viewer.setFocus()

    def _show_mode(self) -> None:
        editing = self._editing
        self.edit_button.blockSignals(True)
        self.edit_button.setChecked(editing)
        self.view_button.setChecked(not editing)
        self.edit_button.blockSignals(False)
        self.title_edit.setReadOnly(not editing)
        self.title_edit.setProperty("editing", editing)
        self.title_edit.style().polish(self.title_edit)
        self.type_box.setVisible(editing)
        self.lock_label.setVisible(not editing and self.note_type() == NoteType.SECURED)
        self.tag_area.set_editable(editing)
        self.footer.setVisible(editing)
        self.body.setCurrentIndex(1 if editing else 0)  # 0: the viewer, or its stand-in until a Note is viewed

    def _render(self) -> None:
        """Show the Body rendered, when a Note is being viewed. Unchanged text isn't loaded again."""
        if not self._open or self._editing:
            return
        text = self.editor.toPlainText()
        if self._viewer is None or self._viewer.markdown() != text:
            self.viewer.set_markdown(text)

    def _type_chosen(self, index: int) -> None:
        """Making a Note Secured needs the Notebook password: created the first time, else typed once a session."""
        if self.type_box.itemData(index) != NoteType.SECURED or self._password.is_unlocked():
            return
        if not self._password.exists():
            new = password_dialogs.create_password(self)
            if new is not None:
                self._password.create(new)
        else:
            password_dialogs.ask_password(self, self._password.unlock)
        if not self._password.is_unlocked():
            self.type_box.setCurrentIndex(self.type_box.findData(NoteType.OPEN))
