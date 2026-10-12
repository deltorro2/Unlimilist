"""A small tooltip-style balloon that explains why something did not happen, then fades away."""

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

_SHOW_MS = 3000


class Balloon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # so the rounded corners show
        self._label = QLabel()
        self._label.setObjectName("balloon")
        self._label.setStyleSheet(
            "QLabel#balloon { background: #2B2D33; color: #FFFFFF; border-radius: 8px;"
            " padding: 8px 12px; font-size: 13px; font-weight: 500; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def text(self) -> str:
        return self._label.text()

    def show_at(self, global_pos: QPoint, text: str) -> None:
        """Show `text` just above `global_pos`."""
        self._label.setText(text)
        self.adjustSize()
        self.move(global_pos - QPoint(self.width() // 2, self.height() + 12))
        self.show()
        self.raise_()
        self._timer.start(_SHOW_MS)
