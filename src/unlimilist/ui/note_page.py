"""Show Note: one Note in place of the Notebook's table.

Three header lines (Back, Title, Type, Delete and the View/Edit switch; the dates; the Tags), then the Body.
View mode renders the Markdown; Edit mode edits the Title, Type, Tags and the raw Markdown. Edits are saved on
leaving Edit mode, on leaving the Note, and every five minutes while Edit mode stays on.
"""

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import QSize, QStringListModel, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
    QTextFrameFormat,
    QTextTable,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QCompleter,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QStackedWidget,
    QTextBrowser,
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
<tr><td>an empty line</td><td>A new paragraph</td></tr>
</table>
"""


def polish(document: QTextDocument) -> None:
    """Give rendered Markdown room to breathe: space after paragraphs, lists and around headings, grey quotes,
    and tables with padded, ruled cells. Qt's Markdown reader sets none of this."""
    cursor = QTextCursor(document)
    for frame in document.rootFrame().childFrames():
        if isinstance(frame, QTextTable):
            _polish_table(frame)
    block = document.begin()
    while block.isValid():
        cursor.setPosition(block.position())
        if cursor.currentTable() is None:
            fmt = block.blockFormat()
            if fmt.headingLevel():
                fmt.setTopMargin(0 if block == document.begin() else 14)
                fmt.setBottomMargin(6)
            elif block.textList() is not None and block.next().textList() is not None:
                fmt.setBottomMargin(3)
            else:
                fmt.setBottomMargin(10)
            cursor.setBlockFormat(fmt)
            if fmt.intProperty(QTextFormat.Property.BlockQuoteLevel):
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                quote = QTextCharFormat()
                quote.setForeground(QColor("#5A5F6B"))
                quote.setFontItalic(True)
                cursor.mergeCharFormat(quote)
        block = block.next()


def _polish_table(table: QTextTable) -> None:
    table_format = table.format()
    table_format.setCellPadding(6)
    table_format.setCellSpacing(0)
    table_format.setBorder(1)
    table_format.setBorderBrush(QColor("#D3D7E0"))
    table_format.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
    table_format.setBorderCollapse(False)
    table_format.setBottomMargin(10)
    table.setFormat(table_format)
    # After a quote, Qt's reader starts the first cell with an empty line, which pushes its text down.
    first = table.cellAt(0, 0)
    start = first.firstCursorPosition()
    if not start.block().text() and start.block().next().position() <= first.lastCursorPosition().position():
        start.movePosition(QTextCursor.MoveOperation.NextBlock)
        start.deletePreviousChar()
    header = QTextCharFormat()  # a Markdown table's first row is its header; Qt doesn't always make it bold
    header.setFontWeight(QFont.Weight.Bold)
    for column in range(table.columns()):
        cell = table.cellAt(0, column)
        cursor = cell.firstCursorPosition()
        cursor.setPosition(cell.lastCursorPosition().position(), QTextCursor.MoveMode.KeepAnchor)
        cursor.mergeCharFormat(header)


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
        self.viewer = QTextBrowser()
        self.viewer.setObjectName("noteViewer")
        self.viewer.setOpenExternalLinks(True)
        self.body = QStackedWidget()
        self.body.addWidget(self.viewer)
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

        body_box = QFrame()
        body_box.setObjectName("noteBody")
        body_layout = QVBoxLayout(body_box)
        body_layout.setContentsMargins(1, 1, 1, 1)
        body_layout.setSpacing(0)
        body_layout.addWidget(self.body, 1)
        body_layout.addWidget(self.footer)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)
        layout.addLayout(line1)
        layout.addWidget(self.dates_label)
        layout.addWidget(self.tag_area)
        layout.addSpacing(4)
        layout.addWidget(body_box, 1)

        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(AUTOSAVE_MS)
        self.autosave_timer.timeout.connect(self.save)
        self._show_mode()

    def set_notebook(self, notebook: Notebook) -> None:
        self._notebook = notebook

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
        self.save()
        self.autosave_timer.stop()
        self._open = False
        self._note_id = None
        self._saved = None
        self._fill("", "", (), NoteType.OPEN)

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
        self._editing = editing
        if editing:
            self.autosave_timer.start()
        else:
            self.autosave_timer.stop()
            self._render()
        self._show_mode()
        if editing:
            self.editor.setFocus()

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
        self.body.setCurrentWidget(self.editor if editing else self.viewer)

    def _render(self) -> None:
        document = self.viewer.document()
        document.setMarkdown(self.editor.toPlainText(), QTextDocument.MarkdownFeature.MarkdownDialectGitHub)
        polish(document)

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
