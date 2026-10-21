"""Startup: the Tasks and Notes load in a background thread while a card with a moving bar covers the faded window."""

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QThread, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from unlimilist.board import Board
from unlimilist.note_search import NoteSearch
from unlimilist.note_store import MarkdownNoteStore
from unlimilist.notebook import Notebook
from unlimilist.store import MarkdownTaskStore
from unlimilist.ui.app_title import RingedLetter

_TITLE = "Getting things ready"
_MESSAGE = "Preparing your workspace…"
_FADE = QColor(246, 247, 250, 185)  # laid over the window while it loads
_TRACK = QColor("#E6EBF2")
_BAR_START, _BAR_END = QColor("#2F6FED"), QColor("#25A99B")
_DOT = QColor("#E53935")
_BAR_PERIOD_MS = 1100
_BAR_SHARE = 0.3  # the moving segment's share of the track
_FADE_OUT_MS = 250


def open_board(folder: Path) -> tuple[Board, list[str]]:
    """Read every Task file and build the Board. Slow with many files, so it runs in the background."""
    store = MarkdownTaskStore(folder)
    board = Board(store=store)
    return board, list(store.warnings)


SEARCH_INDEX = ".search-index.json"  # in the notes folder; the app reads only *.md files there


def open_notebook(folder: Path) -> tuple[Notebook, NoteSearch, list[str]]:
    """Read every Note file, build the Notebook and bring its search index up to date. Secured Notes stay
    encrypted."""
    store = MarkdownNoteStore(folder)
    notebook = Notebook(store=store)
    search = NoteSearch(notebook, index_path=folder / SEARCH_INDEX)
    search.flush()
    return notebook, search, list(store.warnings)


class BoardLoader(QThread):
    """Runs open_board (and open_notebook) off the UI thread; they are handed back through `loaded`."""

    loaded = Signal(object, object, object)  # Board, (Notebook, NoteSearch) or None without a notes folder, warnings
    failed = Signal(str)

    def __init__(self, folder: Path, notes_folder: Path | None = None, parent=None):
        super().__init__(parent)
        self._folder = folder
        self._notes_folder = notes_folder

    def run(self):
        try:
            board, warnings = open_board(self._folder)
            notes = None
            if self._notes_folder is not None:
                notebook, search, note_warnings = open_notebook(self._notes_folder)
                notes = (notebook, search)
                warnings += note_warnings
        except Exception as error:  # e.g. the data folder can't be created or read
            self.failed.emit(str(error))
            return
        self.loaded.emit(board, notes, warnings)


class ProgressBar(QWidget):
    """A rounded track with a gradient segment sliding along it: loading has no percentage to show."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(10)
        self._phase = 0.0
        self._animation = QVariantAnimation(self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(_BAR_PERIOD_MS)
        self._animation.setLoopCount(-1)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._animation.valueChanged.connect(self._advance)
        self._animation.start()

    def phase(self) -> float:
        return self._phase

    def stop(self) -> None:
        self._animation.stop()

    def _advance(self, value) -> None:
        self._phase = float(value)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(self.rect())
        radius = track.height() / 2
        shape = QPainterPath()
        shape.addRoundedRect(track, radius, radius)
        painter.fillPath(shape, _TRACK)

        segment = track.width() * _BAR_SHARE
        left = -segment + self._phase * (track.width() + segment)
        bar = QRectF(left, 0, segment, track.height())
        gradient = QLinearGradient(bar.topLeft(), bar.topRight())
        gradient.setColorAt(0.0, _BAR_START)
        gradient.setColorAt(1.0, _BAR_END)
        painter.setClipPath(shape)
        piece = QPainterPath()
        piece.addRoundedRect(bar, radius, radius)
        painter.fillPath(piece, gradient)
        painter.end()


class PulsingDot(QWidget):
    """A small red dot that fades in and out while loading."""

    def __init__(self, parent=None, size: int = 8):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._opacity = 1.0
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(1000)
        self._animation.setKeyValueAt(0.0, 1.0)
        self._animation.setKeyValueAt(0.5, 0.25)
        self._animation.setKeyValueAt(1.0, 1.0)
        self._animation.setLoopCount(-1)
        self._animation.valueChanged.connect(self._fade)
        self._animation.start()

    def _fade(self, value) -> None:
        self._opacity = float(value)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self._opacity)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_DOT)
        painter.drawEllipse(QRectF(self.rect()))
        painter.end()


class LoadingScreen(QWidget):
    """Covers the whole window, fading it, and blocks clicks; the card sits in the middle."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("loadingScreen")
        self.setAttribute(Qt.WidgetAttribute.WA_NoMousePropagation)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._card = QFrame(self)
        self._card.setObjectName("loadingCard")
        self._card.setFixedSize(540, 260)
        shadow = QGraphicsDropShadowEffect(self._card)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 40))
        self._card.setGraphicsEffect(shadow)

        self._title = QLabel(_TITLE)
        self._title.setObjectName("loadingTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message = QLabel(_MESSAGE)
        self._message.setObjectName("loadingMessage")
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setWordWrap(True)
        self._bar = ProgressBar()
        self._bar.setFixedWidth(380)

        layout = QVBoxLayout(self._card)
        layout.setContentsMargins(40, 26, 40, 40)
        layout.setSpacing(0)
        layout.addWidget(RingedLetter(), 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(16)
        layout.addWidget(self._title)
        layout.addSpacing(8)
        layout.addWidget(self._message)
        layout.addSpacing(26)
        layout.addWidget(self._bar, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

        self._snapshot = None
        self._dot = PulsingDot(self._card)
        self._dot.move(self._card.width() - 84, 36)

        self.setGeometry(parent.rect())
        self.show()
        self.raise_()
        self.setFocus()

    def title(self) -> str:
        return self._title.text()

    def message(self) -> str:
        return self._message.text()

    def bar_phase(self) -> float:
        return self._bar.phase()

    def show_error(self, text: str) -> None:
        self._title.setText("Something went wrong")
        self._message.setText(text)
        self._bar.stop()
        self._dot.hide()

    def fade_out(self, done) -> None:
        """Fade away, then call `done`. The card has a shadow effect, and Qt can't nest an opacity effect
        around it, so the screen fades a picture of itself instead."""
        self._snapshot = self.grab()
        self._card.hide()
        self._opacity = 1.0
        self._fade = QVariantAnimation(self)
        self._fade.setDuration(_FADE_OUT_MS)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.valueChanged.connect(self._set_opacity)
        self._fade.finished.connect(done)
        self._fade.start()

    def _set_opacity(self, value) -> None:
        self._opacity = float(value)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._card.move((self.width() - self._card.width()) // 2, (self.height() - self._card.height()) // 2)

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._snapshot is not None:
            painter.setOpacity(self._opacity)
            painter.drawPixmap(0, 0, self._snapshot)
        else:
            painter.fillRect(self.rect(), _FADE)
        painter.end()

    # The window underneath must not react while loading.
    def mousePressEvent(self, event):
        event.accept()

    def keyPressEvent(self, event):
        event.accept()
