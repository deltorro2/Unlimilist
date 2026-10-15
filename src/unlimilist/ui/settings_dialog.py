"""The Settings window: one tab per area. For now only Board view, with the Card font size."""

from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from unlimilist.domain import Activity, Stage, Task, Urgency
from unlimilist.settings import CARD_FONT_SIZES, Settings
from unlimilist.ui.card import CardWidget
from unlimilist.ui.styling import card_fill

_PREVIEW_WIDTH = 330  # about a card's width on the Board


def _sample_tasks() -> list[Task]:
    """Two made-up Tasks for the preview: a Someday one and a dated one."""
    now = datetime.now()
    return [
        Task(
            id="preview-someday",
            title="Call grandma about the family recipes",
            stage=Stage.INBOX,
            created_at=now,
            details="#family",
            priority=1,
            activity=Activity.PHONE_CALL,
        ),
        Task(
            id="preview-dated",
            title="Pay the electricity bill",
            stage=Stage.INBOX,
            created_at=now,
            details="#finance #home",
            deadline=date.today() + timedelta(days=7),
            activity=Activity.MILESTONE,
        ),
    ]


class SettingsDialog(QDialog):
    """Changes apply at once: the Board follows the slider and the choice is saved, so there is only Close."""

    cardFontSizeChanged = Signal(int)

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setObjectName("settingsDialog")

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_board_view(settings), "Board view")

        self.close_button = QPushButton("Close")
        self.close_button.setDefault(True)
        self.close_button.clicked.connect(self.accept)
        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(self.tabs)
        layout.addLayout(footer)

    def _build_board_view(self, settings: Settings) -> QWidget:
        heading = QLabel("Card font size")
        heading.setObjectName("settingsHeading")

        self.font_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_slider.setObjectName("cardFontSlider")
        self.font_slider.setRange(CARD_FONT_SIZES[0], CARD_FONT_SIZES[-1])
        self.font_slider.setPageStep(1)
        self.font_slider.setTickInterval(1)
        self.font_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.font_slider.setValue(settings.card_font_size)
        self.font_slider.valueChanged.connect(self._font_size_chosen)

        scale = QHBoxLayout()
        scale.setSpacing(10)
        small, largest = QLabel("Small"), QLabel("Largest")
        small.setObjectName("settingsHint")
        largest.setObjectName("settingsHint")
        scale.addWidget(small)
        scale.addWidget(self.font_slider, 1)
        scale.addWidget(largest)

        preview_heading = QLabel("Preview")
        preview_heading.setObjectName("settingsHeading")
        self._preview = QFrame()
        self._preview.setObjectName("settingsPreview")
        self._preview.setFixedWidth(_PREVIEW_WIDTH + 24)
        self._preview_layout = QVBoxLayout(self._preview)
        self._preview_layout.setContentsMargins(12, 12, 12, 12)
        self._preview_layout.setSpacing(10)
        self._preview_cards: list[CardWidget] = []
        self._show_preview(settings.card_font_size)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(heading)
        layout.addLayout(scale)
        layout.addSpacing(8)
        layout.addWidget(preview_heading)
        layout.addWidget(self._preview, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return page

    def preview_cards(self) -> list[CardWidget]:
        return list(self._preview_cards)

    def _font_size_chosen(self, size: int) -> None:
        self._show_preview(size)
        self.cardFontSizeChanged.emit(size)

    def _show_preview(self, size: int) -> None:
        for card in self._preview_cards:
            card.hide()
            card.setParent(None)
            card.deleteLater()
        self._preview_cards = []
        for task in _sample_tasks():
            card = CardWidget(task, Urgency.NONE, card_fill(Stage.INBOX, task.kind, 0, 1), font_size=size)
            card.setFixedWidth(_PREVIEW_WIDTH)
            card.set_draggable(False)  # a preview, not a real Task: it can't be dragged
            card.setCursor(Qt.CursorShape.ArrowCursor)
            self._preview_layout.addWidget(card)
            self._preview_cards.append(card)
        self._preview.adjustSize()
