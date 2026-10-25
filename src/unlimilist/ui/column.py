"""A Column on the Board: one Stage, its Someday cards aligned left and Time-limited cards aligned right."""

from PySide6.QtCore import QEasingCurve, QPoint, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from unlimilist.domain import LaneKind, Stage, Stale, Task, Urgency
from unlimilist.ui.card import CardWidget, decode_drag
from unlimilist.ui.styling import card_fill
from unlimilist.ui.toggle_switch import ToggleSwitch

# While the Tag filter hides some cards, a drop position is ambiguous: a Task moved in from another Stage
# goes to the bottom (rank 999 means the bottom), and reordering within the Stage is refused.
_BOTTOM_INDEX = 998
_FILTERED_REORDER_HINT = "Clear the Tag filter to reorder"
_CARD_SHARE = 3  # a card takes 3 parts of 4, i.e. 75% of the Column width
_GAP_SHARE = 1
_REVEAL_MARGIN = 24  # room left above or below a card the Column jumps to
FOLDED_WIDTH = 90  # Folded Done: a strip just wide enough for its title and switch
_SLIDE_MS = 250
# A Task dropped on Folded Done has no card to highlight, so the strip flashes the landing highlight instead.
_FLASH = QColor("#FFE066")
_FLASH_HOLD_MS = 1000
_FLASH_FADE_MS = 400

_DROP_HINTS = {
    LaneKind.SOMEDAY: "Drop as Someday",
    LaneKind.TIME_LIMITED: "Drop as Time-limited",
}
_CONVERSION_HINTS = {
    LaneKind.SOMEDAY: "Drop as Someday — clears the dates",
    LaneKind.TIME_LIMITED: "Drop as Time-limited — asks for a date",
}


class _Flash(QWidget):
    """Laid over the folded strip: yellow, held, then faded out."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._strength = 0.0
        self._animation = QVariantAnimation(self)
        total = _FLASH_HOLD_MS + _FLASH_FADE_MS
        self._animation.setDuration(total)
        self._animation.setKeyValueAt(0.0, 1.0)
        self._animation.setKeyValueAt(_FLASH_HOLD_MS / total, 1.0)
        self._animation.setKeyValueAt(1.0, 0.0)
        self._animation.valueChanged.connect(self._set_strength)
        self._animation.finished.connect(self.hide)
        self.hide()

    def flash(self) -> None:
        self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()
        self._animation.stop()
        self._animation.start()
        self._set_strength(1.0)

    def is_flashing(self) -> bool:
        return self.isVisible()

    def _set_strength(self, value) -> None:
        self._strength = float(value)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colour = QColor(_FLASH)
        colour.setAlphaF(0.85 * self._strength)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour)
        painter.drawRoundedRect(self.rect(), 8, 8)
        painter.end()


class ColumnWidget(QFrame):
    cardClicked = Signal(str)
    cardMenuRequested = Signal(str, QPoint)
    # task id, target Stage, target LaneKind (None for Done), drop rank index among the Someday cards,
    # and the drop point on screen
    taskDropped = Signal(str, object, object, int, QPoint)

    def __init__(self, stage: Stage, title: str, top_widget: QWidget | None = None, parent=None):
        super().__init__(parent)
        self.stage = stage
        self.setObjectName("stage")
        self.setAcceptDrops(True)

        header = self.header = QLabel(title)
        header.setObjectName("stageHeader")
        # How many of the shown Tasks are Stale; Done never has any.
        self.stale_badge = QLabel()
        self.stale_badge.setObjectName("staleBadge")
        self.stale_badge.setToolTip("Someday Tasks that have waited here longer than allowed")
        self.stale_badge.hide()
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(6)
        title_row.addWidget(header)
        title_row.addWidget(self.stale_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        title_row.addStretch(1)

        self._someday_count = QLabel()
        self._someday_count.setObjectName("laneHeader")
        self._time_limited_count = QLabel()
        self._time_limited_count.setObjectName("laneHeader")
        counts = QHBoxLayout()
        counts.setContentsMargins(6, 0, 6, 0)
        counts.addWidget(self._someday_count)
        counts.addStretch(1)
        counts.addWidget(self._time_limited_count)
        self._time_limited_count.setHidden(stage == Stage.DONE)
        self._counts = [self._someday_count, self._time_limited_count]

        self._hint = QLabel()
        self._hint.setObjectName("laneHint")
        self._hint.hide()

        self._cards: list[CardWidget] = []
        self._rows: list[QWidget] = []
        self._filtered = False
        self._task_ids: set[str] = set()
        self._placeholders: list[QFrame] = []
        self._container = QWidget()
        self._container.setObjectName("laneBody")
        self._stack = QVBoxLayout(self._container)
        self._stack.setContentsMargins(8, 6, 8, 12)
        self._stack.setSpacing(10)
        self._stack.addStretch(1)
        self._indicator = QFrame()
        self._indicator.setObjectName("dropIndicator")
        self._indicator.setFixedHeight(3)
        self._indicator.hide()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self._container)
        self._scroll = scroll
        self._revealing: str | None = None
        self._font_size = 2
        scroll.verticalScrollBar().rangeChanged.connect(self._scroll_to_revealed)
        scroll.verticalScrollBar().actionTriggered.connect(self._stop_revealing)  # the user scrolled

        self._body = QFrame()
        self._body.setObjectName("lane")
        self._set_drop_side(None)
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(4, 6, 4, 4)
        body_layout.setSpacing(4)
        body_layout.addLayout(counts)
        body_layout.addWidget(self._hint)
        body_layout.addWidget(scroll, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 8)
        layout.setSpacing(8)
        layout.addLayout(title_row)
        if top_widget is not None:
            layout.addWidget(top_widget)
        self._folded = False
        self._slide: QVariantAnimation | None = None
        if stage == Stage.DONE:
            self.fold_switch = ToggleSwitch(checked=True)
            self.fold_switch.setObjectName("foldSwitch")
            self.fold_switch.setToolTip("Hide Done")
            layout.addWidget(self.fold_switch, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._body, 1)
        self._flash = _Flash(self._body)

    # Folded Done

    def is_folded(self) -> bool:
        return self._folded

    def is_sliding(self) -> bool:
        return self._slide is not None

    def is_flashing(self) -> bool:
        return self._flash.is_flashing()

    def flash(self) -> None:
        self._flash.flash()

    def slide(self, folded: bool, to_width: int, finished=None) -> None:
        """Fold to the strip, or unfold to `to_width`, sliding. Unfolded, the Column then takes its share of the
        Board again. While folded only the title, the switch and the empty lane (still a drop target) show."""
        self._folded = folded
        self.fold_switch.setToolTip("Show Done" if folded else "Hide Done")
        if folded:
            self._show_lane_contents(False)
        if self._slide is not None:
            self._slide.stop()
        self._slide = QVariantAnimation(self)
        self._slide.setDuration(_SLIDE_MS)
        self._slide.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._slide.setStartValue(self.width())
        self._slide.setEndValue(to_width)
        self._slide.valueChanged.connect(lambda width: self.setFixedWidth(int(width)))

        def done() -> None:
            self._slide = None
            if not folded:
                self.setMinimumWidth(0)
                self.setMaximumWidth(16777215)  # QWIDGETSIZE_MAX: the Board's stretch decides again
                self._show_lane_contents(True)
            if finished is not None:
                finished()

        self._slide.finished.connect(done)
        self._slide.start()

    def _show_lane_contents(self, shown: bool) -> None:
        for label in self._counts:
            label.setVisible(shown and not (label is self._time_limited_count and self.stage == Stage.DONE))
        self._scroll.setVisible(shown)
        if not shown:
            self._hint.hide()

    def drop_hint(self) -> str:
        """The hint shown while a Task is dragged over this Column, or "" when there is none."""
        return "" if self._hint.isHidden() else self._hint.text()

    def cards(self) -> list[CardWidget]:
        """Cards in the order shown, top to bottom."""
        return list(self._cards)

    def reveal(self, task_id: str) -> bool:
        """Highlight the Task's card, and jump to it if it is out of view. False if it isn't shown here."""
        card = self._card(task_id)
        if card is None:
            return False
        if self._folded:
            self.flash()  # its card can't be seen
            return True
        card.highlight()
        # The cards were just rebuilt: Qt shows and lays them out over its next turns, and the Column keeps
        # growing (a scrollbar appears, titles rewrap). So the jump is aimed again each time the scroll range
        # changes, until the highlight ends or the user scrolls.
        self._revealing = task_id
        QTimer.singleShot(0, self, self._scroll_to_revealed)
        return True

    def set_card_font_size(self, size: int) -> None:
        """The Card font size (1 to 5) for the cards made from the next set_tasks on."""
        self._font_size = size

    def scroll_position(self) -> int:
        return self._scroll.verticalScrollBar().value()

    def _scroll_to_revealed(self, *_) -> None:
        card = self._card(self._revealing) if self._revealing else None
        if card is None or not card.is_highlighted():
            self._revealing = None
            return
        self._scroll.ensureWidgetVisible(card.parentWidget(), 0, _REVEAL_MARGIN)

    def _stop_revealing(self, *_) -> None:
        self._revealing = None

    def _card(self, task_id: str) -> CardWidget | None:
        return next((c for c in self._cards if c.task.id == task_id), None)

    def show_placeholders(self, count: int) -> None:
        """Grey tiles standing in for cards while the Tasks load; set_tasks replaces them."""
        self._clear_placeholders()
        for _ in range(count):
            tile = QFrame()
            tile.setObjectName("placeholderTile")
            tile.setFixedHeight(62)
            self._stack.insertWidget(self._stack.count() - 1, tile)
            self._placeholders.append(tile)

    def placeholder_count(self) -> int:
        return len(self._placeholders)

    def _clear_placeholders(self) -> None:
        for tile in self._placeholders:
            tile.setParent(None)
            tile.deleteLater()
        self._placeholders = []

    def lane_headers(self) -> tuple[str, str | None]:
        """The Lane header texts; Done has only one."""
        return self._someday_count.text(), None if self.stage == Stage.DONE else self._time_limited_count.text()

    def set_tasks(
        self,
        tasks: list[Task],
        urgencies: list[Urgency],
        shown: set[str] | None = None,
        stale: dict[str, Stale] | None = None,
    ) -> None:
        """Show `tasks` in order, or only those whose id is in `shown` while the Tag filter is on. The Tasks in
        `stale` are drawn Stale, and the title counts those shown.

        A card keeps the shade of its place among all of `tasks`, so filtering never recolours it.
        """
        stale = stale or {}
        self._clear_placeholders()
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._cards, self._rows = [], []
        self._filtered = shown is not None
        self._task_ids = {t.id for t in tasks}
        for index, (task, urgency) in enumerate(zip(tasks, urgencies)):
            if shown is not None and task.id not in shown:
                continue
            kind = None if self.stage == Stage.DONE else task.kind
            card = CardWidget(
                task,
                urgency,
                card_fill(self.stage, kind, index, len(tasks)),
                font_size=self._font_size,
                stale=stale.get(task.id),
            )
            card.clicked.connect(self.cardClicked)
            card.menuRequested.connect(self.cardMenuRequested)
            row = self._row_for(card)
            self._stack.insertWidget(self._stack.count() - 1, row)
            self._cards.append(card)
            self._rows.append(row)
        visible = [c.task for c in self._cards]
        stale_shown = sum(1 for t in visible if t.id in stale)
        self.stale_badge.setText(f"{stale_shown} stale")
        self.stale_badge.setVisible(stale_shown > 0)
        if self.stage == Stage.DONE:
            self._someday_count.setText(f"COMPLETED  ·  {_count(visible, tasks, self._filtered)}")
        else:
            someday = [t for t in tasks if t.kind == LaneKind.SOMEDAY]
            time_limited = [t for t in tasks if t.kind == LaneKind.TIME_LIMITED]
            shown_someday = [t for t in visible if t.kind == LaneKind.SOMEDAY]
            shown_time_limited = [t for t in visible if t.kind == LaneKind.TIME_LIMITED]
            self._someday_count.setText(f"SOMEDAY  ·  {_count(shown_someday, someday, self._filtered)}")
            self._time_limited_count.setText(
                f"TIME-LIMITED  ·  {_count(shown_time_limited, time_limited, self._filtered)}"
            )

    def _row_for(self, card: CardWidget) -> QWidget:
        row = QWidget()
        row.setObjectName("cardRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        if self.stage == Stage.DONE:
            layout.addWidget(card)
        elif card.task.kind == LaneKind.SOMEDAY:
            layout.addWidget(card, _CARD_SHARE)
            layout.addStretch(_GAP_SHARE)
        else:
            layout.addStretch(_GAP_SHARE)
            layout.addWidget(card, _CARD_SHARE)
        return row

    # Drag and drop

    def _side(self, pos: QPoint) -> LaneKind | None:
        if self.stage == Stage.DONE:
            return None
        return LaneKind.SOMEDAY if pos.x() < self.width() / 2 else LaneKind.TIME_LIMITED

    def dragEnterEvent(self, event):
        if decode_drag(event.mimeData()) is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self._update_drag(event)

    def dragMoveEvent(self, event):
        if decode_drag(event.mimeData()) is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self._update_drag(event)

    def dragLeaveEvent(self, event):
        self._end_drag()

    def dropEvent(self, event):
        dragged = decode_drag(event.mimeData())
        self._end_drag()
        if dragged is None:
            event.ignore()
            return
        if self._reorder_refused(dragged.task_id):
            event.ignore()
            return
        event.acceptProposedAction()
        pos = event.position().toPoint()
        index = _BOTTOM_INDEX if self._filtered else self._someday_index(dragged.task_id, pos)
        self.taskDropped.emit(dragged.task_id, self.stage, self._side(pos), index, self.mapToGlobal(pos))

    def _reorder_refused(self, task_id: str) -> bool:
        return self._filtered and task_id in self._task_ids

    def _update_drag(self, event) -> None:
        task_id, kind, unfinished = decode_drag(event.mimeData())
        pos = event.position().toPoint()
        side = self._side(pos)
        if self.stage == Stage.DONE and unfinished:
            # The Board will refuse it; say why rather than invite the drop.
            self._set_drop_side("blocked")
            self._hint.setText(f"{unfinished} unfinished {'subtask' if unfinished == 1 else 'subtasks'}")
            self._hint.setVisible(not self._folded)  # the strip is too narrow; the balloon says it on drop
            return
        if self._reorder_refused(task_id):
            self._set_drop_side("blocked")
            self._hint.setText(_FILTERED_REORDER_HINT)
            self._hint.show()
            self._indicator.hide()
            return
        self._set_drop_side(side or "all")
        if side is None:
            self._hint.hide()
        else:
            self._hint.setText((_DROP_HINTS if side == kind else _CONVERSION_HINTS)[side])
            self._hint.show()
        if side == LaneKind.SOMEDAY and not self._filtered:
            self._show_indicator(task_id, self._someday_index(task_id, pos))
        else:
            self._indicator.hide()

    def _someday_cards(self, task_id: str) -> list[CardWidget]:
        return [c for c in self._cards if c.task.kind == LaneKind.SOMEDAY and c.task.id != task_id]

    def _someday_index(self, task_id: str, pos: QPoint) -> int:
        """Where a drop at `pos` lands, counted among the other Someday cards."""
        y = self._container.mapFrom(self, pos).y()
        others = self._someday_cards(task_id)
        for index, card in enumerate(others):
            if y < card.parentWidget().geometry().center().y():
                return index
        return len(others)

    def _show_indicator(self, task_id: str, index: int) -> None:
        others = self._someday_cards(task_id)
        self._stack.removeWidget(self._indicator)
        if index < len(others):
            position = self._stack.indexOf(others[index].parentWidget())
        elif others:
            position = self._stack.indexOf(others[-1].parentWidget()) + 1
        else:
            position = 0
        self._stack.insertWidget(position, self._indicator)
        self._indicator.show()

    def _end_drag(self) -> None:
        self._set_drop_side(None)
        self._hint.hide()
        self._indicator.hide()
        self._stack.removeWidget(self._indicator)

    def _set_drop_side(self, side) -> None:
        value = {None: "", "all": "all", "blocked": "blocked", LaneKind.SOMEDAY: "left", LaneKind.TIME_LIMITED: "right"}[
            side
        ]
        self._body.setProperty("dropSide", value)
        self._body.style().unpolish(self._body)
        self._body.style().polish(self._body)


def _count(shown: list[Task], everything: list[Task], filtered: bool) -> str:
    """"5", or "2 of 5" while the Tag filter hides some Tasks."""
    return f"{len(shown)} of {len(everything)}" if filtered else str(len(everything))
