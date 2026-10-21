"""A short message that rises into the middle of the window, stays a moment, then fades away."""

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPoint, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QWidget

SHOW_MS = 2000
_RISE_PX = 24
_RISE_MS = 220
_FADE_MS = 300


class Toast(QLabel):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._rise = QParallelAnimationGroup(self)
        self._move = QPropertyAnimation(self, b"pos", self)
        self._move.setDuration(_RISE_MS)
        self._move.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._appear = QPropertyAnimation(self._opacity, b"opacity", self)
        self._appear.setDuration(_RISE_MS)
        self._rise.addAnimation(self._move)
        self._rise.addAnimation(self._appear)
        self._fade = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade.setDuration(_FADE_MS)
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self.hide)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade.start)
        self.hide()

    def dismiss(self) -> None:
        """Hide at once."""
        self._timer.stop()
        self._rise.stop()
        self._fade.stop()
        self.hide()

    def show_message(self, text: str, ms: int = SHOW_MS) -> None:
        """Show `text` for `ms` milliseconds in all, fading out at the end."""
        self._timer.stop()
        self._fade.stop()
        self.setText(text)
        self.adjustSize()
        parent = self.parentWidget()
        middle = QPoint((parent.width() - self.width()) // 2, (parent.height() - self.height()) // 2)
        self._move.setStartValue(middle + QPoint(0, _RISE_PX))
        self._move.setEndValue(middle)
        self._appear.setStartValue(0.0)
        self._appear.setEndValue(1.0)
        self.move(middle + QPoint(0, _RISE_PX))
        self.raise_()
        self.show()
        self._rise.start()
        self._timer.start(max(0, ms - _FADE_MS))
