import os

# Keep test windows off the screen.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# View mode's web engine draws in software here: there is no GPU off the screen.
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")

from PySide6.QtCore import QCoreApplication, Qt  # noqa: E402

# The web engine must be loaded, and contexts shared, before the QApplication exists (pytest-qt makes it later).
QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
import PySide6.QtWebEngineWidgets  # noqa: E402, F401


def rendered_text(qtbot, viewer, timeout=10000) -> str:
    """The text View mode shows, once the web engine has drawn the page."""
    qtbot.waitUntil(viewer.is_rendered, timeout=timeout)
    answers = []
    viewer.read_text(answers.append)
    qtbot.waitUntil(lambda: bool(answers), timeout=timeout)
    return answers[0]
