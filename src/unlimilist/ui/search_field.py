"""The Notebook's search field: parts of its text can be drawn green (what was found), and Esc clears it."""

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtGui import QColor, QInputMethodEvent, QTextCharFormat
from PySide6.QtWidgets import QLineEdit

GREEN = QColor("#1E9E4A")


class SearchField(QLineEdit):
    escapePressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._green: list[tuple[int, int]] = []
        self.setClearButtonEnabled(True)

    def green_ranges(self) -> list[tuple[int, int]]:
        """(start, length) of each green part."""
        return list(self._green)

    def set_green(self, ranges: list[tuple[int, int]]) -> None:
        """Draw these (start, length) parts green. QLineEdit has no rich text, so the colour goes in as input
        method formatting: drawn only, never part of the text."""
        self._green = list(ranges)
        attributes = []
        for start, length in ranges:
            fmt = QTextCharFormat()
            fmt.setForeground(GREEN)
            attributes.append(
                QInputMethodEvent.Attribute(
                    QInputMethodEvent.AttributeType.TextFormat, start - self.cursorPosition(), length, fmt
                )
            )
        QCoreApplication.sendEvent(self, QInputMethodEvent("", attributes))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.escapePressed.emit()
            return
        super().keyPressEvent(event)
