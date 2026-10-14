"""The sidebar: the views ("Everything"), then the Tags as bubbles that make up the Tag filter."""

import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from unlimilist.ui.flow_layout import FlowLayout

_WIDTH = 190


class TagBubble(QLabel):
    """One Tag with its count; clicking it selects or unselects the Tag."""

    clicked = Signal(str)

    def __init__(self, tag: str, count: int, selected: bool, parent=None):
        super().__init__(parent)
        self.tag = tag
        self.count = count
        self._selected = selected
        self.setObjectName("tagBubble")
        self.setProperty("selected", selected)
        count_colour = "#C9D8FF" if selected else "#8A8F99"
        self.setText(f'#{html.escape(tag)} <span style="color: {count_colour};">{count}</span>')
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def is_selected(self) -> bool:
        return self._selected

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.tag)
        super().mouseReleaseEvent(event)


class Sidebar(QFrame):
    tagClicked = Signal(str)  # the Tag's key, i.e. its case-folded name
    clearClicked = Signal()
    everythingClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebarPane")
        self.setFixedWidth(_WIDTH)

        self.views = QListWidget()
        self.views.setObjectName("sidebar")
        self.views.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.views.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        everything = QListWidgetItem("Everything")
        self.views.addItem(everything)
        placeholder = QListWidgetItem("TBD")
        placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
        self.views.addItem(placeholder)
        self.views.setCurrentItem(everything)
        self.views.setFixedHeight(96)
        self.views.itemClicked.connect(lambda item: item is everything and self.everythingClicked.emit())

        separator = QFrame()
        separator.setObjectName("tagSeparator")
        separator.setFixedHeight(1)

        # The header and its Clear button stay put; only the bubbles below them scroll.
        title = QLabel("TAGS")
        title.setObjectName("tagsHeader")
        self.clear_button = QPushButton()
        self.clear_button.setObjectName("clearTags")
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clear_button.clicked.connect(self.clearClicked)
        header = QHBoxLayout()
        header.setContentsMargins(16, 10, 10, 4)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.clear_button)

        self._cloud = QWidget()
        self._cloud.setObjectName("tagCloud")
        self._flow = FlowLayout(self._cloud)
        self._flow.setContentsMargins(12, 4, 10, 12)
        scroll = QScrollArea()
        scroll.setObjectName("tagScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self._cloud)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.views)
        layout.addWidget(separator)
        layout.addLayout(header)
        layout.addWidget(scroll, 1)

        self._bubbles: list[TagBubble] = []
        self.set_tags([], frozenset())

    def tag_bubbles(self) -> list[TagBubble]:
        return list(self._bubbles)

    def set_tags(self, tags: list[tuple[str, int]], selected: frozenset[str]) -> None:
        """Show `tags` (name, count) as bubbles; those whose key is in `selected` are drawn selected."""
        for bubble in self._bubbles:
            # Detached at once: a bubble may be mid-click, so it is only deleted later.
            self._flow.removeWidget(bubble)
            bubble.hide()
            bubble.setParent(None)
            bubble.deleteLater()
        self._bubbles = []
        for name, count in tags:
            bubble = TagBubble(name, count, name.casefold() in selected)
            bubble.clicked.connect(lambda tag: self.tagClicked.emit(tag.casefold()))
            self._flow.addWidget(bubble)
            self._bubbles.append(bubble)
        self.clear_button.setEnabled(bool(selected))
        self.clear_button.setText(f"✕ Clear ({len(selected)})" if selected else "✕ Clear")
