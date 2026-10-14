"""A small WYSIWYG editor whose content is read and written as Markdown."""

import re
from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QUrl
from PySide6.QtGui import (
    QDesktopServices,
    QSyntaxHighlighter,
    QFont,
    QFontDatabase,
    QKeySequence,
    QShortcut,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextListFormat,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from unlimilist.domain import TAG
from unlimilist.ui.icons import icon


class _LinkAwareTextEdit(QTextEdit):
    """Opens links on ⌘-click (Ctrl-click elsewhere); a plain click keeps editing."""

    def mouseReleaseEvent(self, event):
        anchor = self.anchorAt(event.position().toPoint())
        if anchor and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            QDesktopServices.openUrl(QUrl(anchor))
            return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        over_link = bool(self.anchorAt(event.position().toPoint()))
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor if over_link else Qt.CursorShape.IBeamCursor)
        super().mouseMoveEvent(event)


class _TagHighlighter(QSyntaxHighlighter):
    """Underlines Tags as they are typed. The underline is only drawn; it is never saved with the text."""

    def highlightBlock(self, text: str) -> None:
        underline = QTextCharFormat()
        underline.setFontUnderline(True)
        for match in TAG.finditer(text):
            length = len(match.group(0)) - (len(match.group(1)) - len(match.group(1).rstrip("-")))
            if not self._in_code_or_link(match.start()):
                self.setFormat(match.start(), length, underline)

    def _in_code_or_link(self, position: int) -> bool:
        fragments = self.currentBlock().begin()
        while not fragments.atEnd():
            fragment = fragments.fragment()
            start = fragment.position() - self.currentBlock().position()
            if start <= position < start + fragment.length():
                fmt = fragment.charFormat()
                return fmt.fontFixedPitch() or fmt.isAnchor()
            fragments += 1
        return False


# The Tag being typed: a # that starts a word, then at least a letter, right before the cursor.
_TYPED_TAG = re.compile(r"(?<![^\s(\[{])#([^\W\d_][\w-]*)$")
_ACCEPT_KEYS = (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab)


class _TagCompleter(QObject):
    """Suggests existing Tags while a Tag is typed: Up/Down pick, Enter or Tab insert, Esc closes."""

    def __init__(self, text_edit: QTextEdit, suggest: Callable[[str], list[str]]):
        super().__init__(text_edit)
        self._text_edit = text_edit
        self._suggest = suggest
        self._typing = False
        # A window of its own, but owned by the editor: macOS then keeps it at the level of the (modal) Task
        # dialog. Without an owner it opened behind the dialog and the suggestions could not be seen.
        self.popup = QListWidget(text_edit)
        self.popup.setObjectName("tagPopup")
        self.popup.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.popup.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.popup.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.popup.itemClicked.connect(self._insert)
        text_edit.installEventFilter(self)
        text_edit.textChanged.connect(self._text_changed)
        text_edit.cursorPositionChanged.connect(self._cursor_moved)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress:
            if not self.popup.isHidden() and self._navigate(event.key()):
                return True
            self._typing = True  # only typed text, not text set by code, opens the suggestions
        elif event.type() == QEvent.Type.KeyRelease:
            self._typing = False
        elif event.type() == QEvent.Type.FocusOut:
            self.popup.hide()
        return False

    def _navigate(self, key) -> bool:
        row = self.popup.currentRow()
        if key == Qt.Key.Key_Down:
            self.popup.setCurrentRow(min(row + 1, self.popup.count() - 1))
        elif key == Qt.Key.Key_Up:
            self.popup.setCurrentRow(max(row - 1, 0))
        elif key in _ACCEPT_KEYS:
            self._insert(self.popup.currentItem())
        elif key == Qt.Key.Key_Escape:
            self.popup.hide()
        else:
            return False
        return True

    def _typed_tag(self) -> str | None:
        cursor = self._text_edit.textCursor()
        before = cursor.block().text()[: cursor.positionInBlock()]
        match = _TYPED_TAG.search(before)
        return match.group(1) if match else None

    def _text_changed(self) -> None:
        if self._typing:
            self._update()

    def _cursor_moved(self) -> None:
        if not self.popup.isHidden() and self._typed_tag() is None:
            self.popup.hide()

    def _update(self) -> None:
        typed = self._typed_tag()
        names = self._suggest(typed) if typed else []
        if not names:
            self.popup.hide()
            return
        self.popup.clear()
        for name in names:
            item = QListWidgetItem(f"#{name}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.popup.addItem(item)
        self.popup.setCurrentRow(0)
        row_height = self.popup.sizeHintForRow(0)
        width = max(self.popup.sizeHintForColumn(0) + 28, 160)
        self.popup.resize(width, row_height * len(names) + 8)
        corner = self._text_edit.cursorRect().bottomLeft()
        self.popup.move(self._text_edit.viewport().mapToGlobal(corner))
        self.popup.show()

    def _insert(self, item: QListWidgetItem | None) -> None:
        typed = self._typed_tag()
        self.popup.hide()
        if item is None or typed is None:
            return
        cursor = self._text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, len(typed) + 1)
        cursor.insertText(f"#{item.data(Qt.ItemDataRole.UserRole)} ")
        self._text_edit.setTextCursor(cursor)


def _is_subtask(block) -> bool:
    # Qt's Markdown import can leave a marker on the paragraph after a list, so the list itself is checked too.
    return (
        block.isValid()
        and block.textList() is not None
        and block.blockFormat().marker() != QTextBlockFormat.MarkerType.NoMarker
    )


class RichTextEditor(QWidget):
    def __init__(
        self,
        placeholder: str = "",
        parent=None,
        subtasks: bool = False,
        suggest_tags: Callable[[str], list[str]] | None = None,
    ):
        """`subtasks` adds the "Add subtask" button. `suggest_tags` turns on Tags: they are underlined, and
        typing one suggests existing Tags from it. Details has both; Usable data has neither."""
        super().__init__(parent)
        self.text_edit = _LinkAwareTextEdit()
        self._tag_highlighter = _TagHighlighter(self.text_edit.document()) if suggest_tags else None
        self._tag_completer = _TagCompleter(self.text_edit, suggest_tags) if suggest_tags else None
        self.tag_popup = self._tag_completer.popup if self._tag_completer else None
        self.text_edit.setPlaceholderText(placeholder)
        self.text_edit.setMouseTracking(True)
        self.text_edit.setToolTip("⌘-click a link to open it")

        self.text_edit.setObjectName("editorText")
        self.text_edit.setFrameShape(QFrame.Shape.NoFrame)

        toolbar_widget = QWidget()
        toolbar_widget.setObjectName("editorToolbar")
        toolbar = QHBoxLayout(toolbar_widget)
        toolbar.setContentsMargins(10, 6, 10, 6)
        toolbar.setSpacing(4)
        for name, tip, handler in [
            ("bold", "Bold (⌘B)", self._toggle_bold),
            ("italic", "Italic (⌘I)", self._toggle_italic),
            ("strikethrough", "Strikethrough", self._toggle_strike),
            (None, None, None),
            ("list", "Bulleted list", lambda: self._make_list(QTextListFormat.Style.ListDisc)),
            ("list-ordered", "Numbered list", lambda: self._make_list(QTextListFormat.Style.ListDecimal)),
            ("code", "Code", self._toggle_code),
            ("link", "Link", self._insert_link),
        ]:
            if name is None:
                separator = QFrame()
                separator.setObjectName("toolbarSeparator")
                separator.setFixedSize(1, 18)
                toolbar.addWidget(separator)
                continue
            button = QToolButton()
            button.setObjectName("editorButton")
            button.setIcon(icon(name))
            button.setIconSize(QSize(18, 18))
            button.setToolTip(tip)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(handler)
            toolbar.addWidget(button)
        self.add_subtask_button = None
        if subtasks:
            separator = QFrame()
            separator.setObjectName("toolbarSeparator")
            separator.setFixedSize(1, 18)
            toolbar.addWidget(separator)
            self.add_subtask_button = QToolButton()
            self.add_subtask_button.setObjectName("editorButton")
            self.add_subtask_button.setIcon(icon("list-todo"))
            self.add_subtask_button.setIconSize(QSize(18, 18))
            self.add_subtask_button.setText("Add subtask")
            self.add_subtask_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self.add_subtask_button.setToolTip("Add a Subtask after the last one, above the other text")
            self.add_subtask_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.add_subtask_button.clicked.connect(self.add_subtask)
            toolbar.addWidget(self.add_subtask_button)
        toolbar.addStretch(1)
        for sequence, handler in [
            (QKeySequence.StandardKey.Bold, self._toggle_bold),
            (QKeySequence.StandardKey.Italic, self._toggle_italic),
        ]:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)

        box = QFrame()
        box.setObjectName("editorBox")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(1, 1, 1, 1)
        box_layout.setSpacing(0)
        box_layout.addWidget(toolbar_widget)
        box_layout.addWidget(self.text_edit, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(box)

        # The dialog shares its height between editors by stretch, so ask only for the toolbar and two lines.
        two_lines = 2 * self.text_edit.fontMetrics().lineSpacing() + 28
        self.setMinimumHeight(toolbar_widget.sizeHint().height() + two_lines)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)

    def markdown(self) -> str:
        if not self.text_edit.toPlainText().strip():
            return ""
        return self.text_edit.document().toMarkdown(QTextDocument.MarkdownFeature.MarkdownDialectGitHub).strip()

    def set_markdown(self, text: str) -> None:
        self.text_edit.document().setMarkdown(text, QTextDocument.MarkdownFeature.MarkdownDialectGitHub)

    def add_subtask(self) -> None:
        """Start an empty Subtask after the last Subtask at the top, before any other text."""
        document = self.text_edit.document()
        last = None
        block = document.firstBlock()
        while _is_subtask(block):
            last, block = block, block.next()
        cursor = QTextCursor(document)
        if last is not None:
            cursor.setPosition(last.position() + last.length() - 1)
            cursor.insertBlock()
        else:
            if document.characterCount() > 1:  # some text already: open an empty block above it
                cursor.insertBlock()
                cursor.movePosition(QTextCursor.MoveOperation.PreviousBlock)
            cursor.setBlockFormat(QTextBlockFormat())
            cursor.setBlockCharFormat(QTextCharFormat())
            cursor.createList(QTextListFormat.Style.ListDisc)
        block_format = cursor.blockFormat()
        block_format.setMarker(QTextBlockFormat.MarkerType.Unchecked)
        cursor.setBlockFormat(block_format)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.setFocus()

    def _merge(self, fmt: QTextCharFormat) -> None:
        self.text_edit.mergeCurrentCharFormat(fmt)
        self.text_edit.setFocus()

    def _toggle_bold(self) -> None:
        fmt = QTextCharFormat()
        bold = self.text_edit.fontWeight() != QFont.Weight.Bold
        fmt.setFontWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
        self._merge(fmt)

    def _toggle_italic(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self.text_edit.fontItalic())
        self._merge(fmt)

    def _toggle_strike(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(not self.text_edit.currentCharFormat().fontStrikeOut())
        self._merge(fmt)

    def _toggle_code(self) -> None:
        fmt = QTextCharFormat()
        is_code = self.text_edit.currentCharFormat().fontFixedPitch()
        if is_code:
            fmt.setFontFamilies([self.text_edit.font().family()])
            fmt.setFontFixedPitch(False)
        else:
            fmt.setFontFamilies([QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()])
            fmt.setFontFixedPitch(True)
        self._merge(fmt)

    def _make_list(self, style: QTextListFormat.Style) -> None:
        cursor = self.text_edit.textCursor()
        current = cursor.currentList()
        if current and current.format().style() == style:
            block_format = cursor.blockFormat()
            current.remove(cursor.block())
            block_format.setIndent(0)
            cursor.setBlockFormat(block_format)
        else:
            cursor.createList(style)
        self.text_edit.setFocus()

    def _insert_link(self) -> None:
        cursor = self.text_edit.textCursor()
        url, ok = QInputDialog.getText(self, "Insert link", "URL:")
        if not ok or not url.strip():
            return
        fmt = QTextCharFormat()
        fmt.setAnchor(True)
        fmt.setAnchorHref(url.strip())
        fmt.setFontUnderline(True)
        fmt.setForeground(self.palette().link())
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        else:
            cursor.insertText(url.strip(), fmt)
        self.text_edit.setFocus()
