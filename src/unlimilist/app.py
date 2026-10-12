"""Starts Unlimilist."""

import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from unlimilist.board import Board
from unlimilist.store import MarkdownTaskStore
from unlimilist.ui.main_window import MainWindow

STYLESHEET = """
QMainWindow, QWidget#central { background: #F4F5F8; }
QToolBar { background: #FFFFFF; border: none; border-bottom: 1px solid #E2E4EA; padding: 4px 8px; spacing: 8px; }
QToolBar QToolButton { background: #2F6FED; color: white; border-radius: 6px; padding: 5px 12px; font-weight: 600; }
QToolBar QToolButton:hover { background: #255CD0; }

QListWidget#sidebar { background: #ECEEF3; border: none; border-right: 1px solid #DDE0E7; padding: 10px 6px; font-size: 14px; color: #1B1B1F; }
QListWidget#sidebar::item { padding: 8px 10px; border-radius: 6px; }
QListWidget#sidebar::item:selected { background: #D7E3FC; color: #1A3D8F; font-weight: 600; }
QListWidget#sidebar::item:disabled { color: #A0A4AE; font-style: italic; }

QFrame#stage { background: #E8EAF0; border-radius: 10px; }
QLabel#stageHeader { font-size: 16px; font-weight: 700; color: #22252B; padding: 2px 4px; }
QFrame#lane { background: #F6F7FA; border: 1px solid #DCDFE6; border-radius: 8px; }
QFrame#lane[dropSide="all"] { background: #EAF1FF; border: 2px dashed #2F6FED; }
QFrame#lane[dropSide="left"] { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #E3EDFF, stop:0.499 #E3EDFF, stop:0.5 #F6F7FA, stop:1 #F6F7FA); border: 2px dashed #2F6FED; }
QFrame#lane[dropSide="right"] { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F6F7FA, stop:0.499 #F6F7FA, stop:0.5 #E0F5F1, stop:1 #E0F5F1); border: 2px dashed #1E9E8A; }
QWidget#cardRow { background: transparent; }
QLabel#laneHeader { font-size: 12px; font-weight: 600; color: #5A5F6B; padding: 2px 6px; text-transform: uppercase; }
QLabel#laneHint { font-size: 11px; color: #2F6FED; padding: 0 6px; }
QWidget#laneBody { background: transparent; }
QFrame#dropIndicator { background: #2F6FED; border-radius: 1px; }
QScrollArea { background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QLineEdit#quickAdd { background: #FFFFFF; border: 1px solid #D0D4DC; border-radius: 6px; padding: 6px 8px; color: #1B1B1F; }
QLineEdit#quickAdd:focus { border: 1px solid #2F6FED; }
"""


def _light_palette() -> QPalette:
    palette = QPalette()
    for role, colour in [
        (QPalette.ColorRole.Window, "#F4F5F8"),
        (QPalette.ColorRole.WindowText, "#1B1B1F"),
        (QPalette.ColorRole.Base, "#FFFFFF"),
        (QPalette.ColorRole.AlternateBase, "#F0F1F5"),
        (QPalette.ColorRole.Text, "#1B1B1F"),
        (QPalette.ColorRole.PlaceholderText, "#9095A0"),
        (QPalette.ColorRole.Button, "#FFFFFF"),
        (QPalette.ColorRole.ButtonText, "#1B1B1F"),
        (QPalette.ColorRole.Highlight, "#2F6FED"),
        (QPalette.ColorRole.HighlightedText, "#FFFFFF"),
        (QPalette.ColorRole.Link, "#2F6FED"),
        (QPalette.ColorRole.ToolTipBase, "#FFFFFF"),
        (QPalette.ColorRole.ToolTipText, "#1B1B1F"),
    ]:
        palette.setColor(role, QColor(colour))
    return palette


def tasks_folder() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(base) / "tasks"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Unlimilist")
    app.setStyle("Fusion")
    app.setPalette(_light_palette())
    app.setStyleSheet(STYLESHEET)

    store = MarkdownTaskStore(tasks_folder())
    board = Board(store=store)
    window = MainWindow(board, warnings=store.warnings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
