"""View mode's Body: the Note rendered as a web page (see note_html), so Mermaid diagrams can be drawn. Links open in
the system browser, never inside the app; only Copy and Select All are on the right-click menu."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMenu

from unlimilist.note_html import render_html

_ASSETS = Path(__file__).resolve().parent.parent / "assets" / "mermaid"


class _Page(QWebEnginePage):
    def acceptNavigationRequest(self, url: QUrl, kind, is_main_frame: bool) -> bool:
        if kind == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            QDesktopServices.openUrl(url)
            return False
        return True


_POLL_MS = 40


class NoteViewer(QWebEngineView):
    findDone = Signal(int, int)  # Find in Note's answer: the active match (1-based, 0 if none) and how many
    rendered = Signal()  # the page is loaded and every diagram drawn

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("noteViewer")
        self.setPage(_Page(self))
        self.setAcceptDrops(False)  # a dropped file would replace the Note with itself
        self._markdown = ""
        self._rendered = False
        self._poll = QTimer(self)
        self._poll.setSingleShot(True)
        self._poll.setInterval(_POLL_MS)
        self._poll.timeout.connect(self._check_rendered)
        self.loadFinished.connect(lambda ok: self._poll.start())
        self.page().findTextFinished.connect(
            lambda result: self.findDone.emit(result.activeMatch(), result.numberOfMatches())
        )

    def markdown(self) -> str:
        return self._markdown

    def set_markdown(self, markdown: str) -> None:
        self._markdown = markdown
        self._rendered = False
        self._poll.stop()
        self.setHtml(render_html(markdown), QUrl.fromLocalFile(f"{_ASSETS}/"))

    def is_rendered(self) -> bool:
        return self._rendered

    def read_text(self, answer: Callable[[str], None]) -> None:
        """The text as shown (diagrams' labels included), handed to `answer` once the engine replies."""
        self.page().runJavaScript("document.body.innerText", 0, lambda text: answer(text or ""))

    def _check_rendered(self) -> None:
        """Diagrams draw after the page loads: wait for the page to say they are done."""

        def answer(done) -> None:
            if done == "done":
                self._rendered = True
                self.rendered.emit()
            else:
                self._poll.start()

        self.page().runJavaScript("document.body ? document.body.dataset.diagrams : ''", 0, answer)

    def find(self, text: str) -> None:
        """Highlight the next place holding `text` (ignoring case), wrapping to the top; answers with findDone."""
        self.page().findText(text)

    def clear_find(self) -> None:
        self.page().findText("")

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction(self.pageAction(QWebEnginePage.WebAction.Copy))
        menu.addAction(self.pageAction(QWebEnginePage.WebAction.SelectAll))
        menu.exec(event.globalPos())
