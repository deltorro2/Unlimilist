"""A pill-shaped on/off switch: blue with the knob on the right when on, grey with the knob on the left when off."""

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton

_ON = QColor("#2F6FED")
_OFF = QColor("#C3C7D0")
_KNOB = QColor("#FFFFFF")
_SLIDE_MS = 150


class ToggleSwitch(QAbstractButton):
    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self.sizeHint())
        self._position = 1.0 if checked else 0.0  # 0 = knob left (off), 1 = knob right (on)
        self._slide = QVariantAnimation(self)
        self._slide.setDuration(_SLIDE_MS)
        self._slide.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._slide.valueChanged.connect(self._move_knob)
        self.toggled.connect(self._toggled)

    def sizeHint(self) -> QSize:
        return QSize(34, 20)

    def _toggled(self, checked: bool) -> None:
        self._slide.stop()
        self._slide.setStartValue(self._position)
        self._slide.setEndValue(1.0 if checked else 0.0)
        self._slide.start()

    def _move_knob(self, value) -> None:
        self._position = float(value)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        track = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        colour = QColor.fromRgbF(
            *(o * self._position + f * (1 - self._position) for o, f in zip(_ON.getRgbF()[:3], _OFF.getRgbF()[:3]))
        )
        if not self.isEnabled():
            colour.setAlphaF(0.45)
        painter.setBrush(colour)
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        margin = 2.0
        size = track.height() - 2 * margin
        left = track.left() + margin + self._position * (track.width() - size - 2 * margin)
        painter.setBrush(_KNOB)
        painter.drawEllipse(QRectF(left, track.top() + margin, size, size))
        painter.end()
