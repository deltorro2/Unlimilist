"""A small WYSIWYG editor whose content is read and written as Markdown."""

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import (
    QDesktopServices,
    QFont,
    QFontDatabase,
    QKeySequence,
    QTextCharFormat,
    QTextDocument,
    QTextListFormat,
)
from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QTextEdit, QToolButton, QVBoxLayout, QWidget


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


class RichTextEditor(QWidget):
    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.text_edit = _LinkAwareTextEdit()
        self.text_edit.setPlaceholderText(placeholder)
        self.text_edit.setMouseTracking(True)
        self.text_edit.setToolTip("⌘-click a link to open it")

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(2)
        for label, tip, shortcut, handler in [
            ("B", "Bold", QKeySequence.StandardKey.Bold, self._toggle_bold),
            ("I", "Italic", QKeySequence.StandardKey.Italic, self._toggle_italic),
            ("S", "Strikethrough", None, self._toggle_strike),
            ("•", "Bulleted list", None, lambda: self._make_list(QTextListFormat.Style.ListDisc)),
            ("1.", "Numbered list", None, lambda: self._make_list(QTextListFormat.Style.ListDecimal)),
            ("</>", "Code", None, self._toggle_code),
            ("🔗", "Link", None, self._insert_link),
        ]:
            button = QToolButton()
            button.setText(label)
            button.setToolTip(tip)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(handler)
            if shortcut is not None:
                button.setShortcut(QKeySequence(shortcut))
            toolbar.addWidget(button)
        toolbar.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addLayout(toolbar)
        layout.addWidget(self.text_edit)

    def markdown(self) -> str:
        if not self.text_edit.toPlainText().strip():
            return ""
        return self.text_edit.document().toMarkdown(QTextDocument.MarkdownFeature.MarkdownDialectGitHub).strip()

    def set_markdown(self, text: str) -> None:
        self.text_edit.document().setMarkdown(text, QTextDocument.MarkdownFeature.MarkdownDialectGitHub)

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
