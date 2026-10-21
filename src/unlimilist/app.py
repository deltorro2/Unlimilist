"""Starts Unlimilist."""

import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

import unlimilist
from unlimilist import data_folders
from unlimilist.board import Board
from unlimilist.data_folders import is_test_build
from unlimilist.notebook_password import KeychainVault, NotebookPassword
from unlimilist.settings import SettingsStore
from unlimilist.ui.icons import app_icon
from unlimilist.ui.main_window import MainWindow

STYLESHEET = """
QMainWindow, QWidget#central { background: #F4F5F8; }
QToolBar { background: #FFFFFF; border: none; border-bottom: 1px solid #E2E4EA; padding: 4px 8px; spacing: 8px; }
QToolBar QToolButton { background: #2F6FED; color: white; border-radius: 6px; padding: 5px 12px; font-weight: 600; }
QToolBar QToolButton:hover { background: #255CD0; }
QToolBar QToolButton#deleteTaskButton { background: #E53935; }
QToolBar QToolButton#deleteTaskButton:hover { background: #C62828; }
QToolBar QToolButton:disabled { background: #B8C6E6; }
QToolBar QToolButton#deleteTaskButton:disabled { background: #EFB3B1; }
QToolBar QToolButton#settingsButton, QToolBar QToolButton#settingsButton:disabled { background: transparent; padding: 4px; }
QToolBar QToolButton#settingsButton:hover { background: #EEF0F4; }

QFrame#sidebarPane { background: #ECEEF3; border: none; border-right: 1px solid #DDE0E7; }
QListWidget#sidebar { background: #ECEEF3; border: none; padding: 10px 6px 4px 6px; font-size: 14px; color: #1B1B1F; }
QListWidget#sidebar::item { padding: 8px 10px; border-radius: 6px; }
QListWidget#sidebar::item:selected { background: #D7E3FC; color: #1A3D8F; font-weight: 600; }
QListWidget#sidebar::item:disabled { color: #A0A4AE; font-style: italic; }
QFrame#tagSeparator { background: #D3D7E0; margin: 0 12px; }
QLabel#tagsHeader { color: #6B7080; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
QPushButton#clearTags { background: transparent; border: none; color: #2F6FED; font-size: 12px; font-weight: 600; padding: 2px 4px; }
QPushButton#clearTags:disabled { color: #B3B8C4; }
QScrollArea#tagScroll, QWidget#tagCloud { background: transparent; border: none; }
QLabel#tagBubble { background: #FFFFFF; border: 1px solid #D3D7E0; border-radius: 9px; padding: 2px 8px; font-size: 12px; color: #2A2E37; }
QLabel#tagBubble:hover { border: 1px solid #2F6FED; }
QLabel#tagBubble[selected="true"] { background: #2F6FED; border: 1px solid #2F6FED; color: #FFFFFF; }
QListWidget#tagPopup { background: #FFFFFF; border: 1px solid #D0D4DC; border-radius: 6px; padding: 3px; font-size: 13px; color: #1A3D8F; }
QListWidget#tagPopup::item { padding: 3px 8px; border-radius: 4px; }
QListWidget#tagPopup::item:selected { background: #D7E3FC; color: #1A3D8F; }

QFrame#stage { background: #E8EAF0; border-radius: 10px; }
QLabel#stageHeader { font-size: 16px; font-weight: 700; color: #22252B; padding: 2px 4px; }
QFrame#lane { background: #F6F7FA; border: 1px solid #DCDFE6; border-radius: 8px; }
QFrame#lane[dropSide="all"] { background: #EAF1FF; border: 2px dashed #2F6FED; }
QFrame#lane[dropSide="left"] { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #E3EDFF, stop:0.499 #E3EDFF, stop:0.5 #F6F7FA, stop:1 #F6F7FA); border: 2px dashed #2F6FED; }
QFrame#lane[dropSide="right"] { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F6F7FA, stop:0.499 #F6F7FA, stop:0.5 #E0F5F1, stop:1 #E0F5F1); border: 2px dashed #1E9E8A; }
QFrame#lane[dropSide="blocked"] { background: #F6F7FA; border: 2px dashed #C9CCD3; }
QWidget#cardRow { background: transparent; }
QLabel#laneHeader { font-size: 12px; font-weight: 600; color: #5A5F6B; padding: 2px 6px; text-transform: uppercase; }
QLabel#laneHint { font-size: 11px; color: #2F6FED; padding: 0 6px; }
QFrame#lane[dropSide="blocked"] QLabel#laneHint { color: #D32F2F; }
QWidget#laneBody { background: transparent; }
QFrame#dropIndicator { background: #2F6FED; border-radius: 1px; }
QScrollArea { background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QLineEdit#quickAdd { background: #FFFFFF; border: 1px solid #D0D4DC; border-radius: 6px; padding: 6px 8px; color: #1B1B1F; }
QLineEdit#quickAdd:focus { border: 1px solid #2F6FED; }
QFrame#placeholderTile { background: #E9ECF2; border: none; border-radius: 6px; }
QFrame#loadingCard { background: #FFFFFF; border: 1px solid #E4E7EE; border-radius: 14px; }
QDialog#settingsDialog { background: #F4F5F8; }
QLabel#settingsHeading { font-size: 13px; font-weight: 700; color: #22252B; }
QLabel#settingsHint { font-size: 12px; color: #6B7080; }
QFrame#settingsPreview { background: #FFFFFF; border: 1px solid #E2E4EA; border-radius: 8px; }
QStackedWidget { background: #F4F5F8; }
QTableWidget#notesTable { background: #FFFFFF; border: 1px solid #E2E4EA; border-radius: 8px; font-size: 13px; color: #1B1B1F; }
QTableWidget#notesTable::item { padding: 0 8px; border-bottom: 1px solid #EEF0F4; }
QTableWidget#notesTable QHeaderView::section { background: #F6F7FA; color: #5A5F6B; font-size: 12px; font-weight: 600; border: none; border-bottom: 1px solid #E2E4EA; padding: 6px 8px; }
QTableWidget#notesTable QHeaderView::section:hover { color: #1A3D8F; }
QLabel#notesEmpty { color: #8A8F99; font-size: 14px; }
QWidget#notePage { background: #F4F5F8; }
QToolButton#noteBack { background: transparent; border: none; color: #2F6FED; font-size: 13px; font-weight: 600; padding: 4px 6px; }
QToolButton#noteBack:hover { background: #E3EDFF; border-radius: 6px; }
QLineEdit#noteTitle { background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 3px 6px; font-size: 18px; font-weight: 700; color: #1B1B1F; }
QLineEdit#noteTitle[editing="true"] { background: #FFFFFF; border: 1px solid #D0D4DC; }
QLineEdit#noteTitle[editing="true"]:focus { border: 1px solid #2F6FED; }
QComboBox#noteType { padding: 3px 8px; min-width: 96px; }
QToolButton#noteDelete { background: transparent; border: none; padding: 4px; border-radius: 6px; }
QToolButton#noteDelete:hover { background: #FDECEA; }
QFrame#modeSwitch { background: #E3E6EC; border-radius: 7px; }
QToolButton#modeButton { background: transparent; border: none; border-radius: 5px; padding: 3px 12px; font-size: 12px; font-weight: 600; color: #5A5F6B; }
QToolButton#modeButton:checked { background: #FFFFFF; color: #1A3D8F; }
QLabel#noteDates { color: #8A8F99; font-size: 11px; padding-left: 8px; }
QLabel#noteTagsHeader { color: #6B7080; font-size: 11px; font-weight: 700; letter-spacing: 1px; padding: 3px 4px 0 8px; }
QFrame#noteTag { background: #FFFFFF; border: 1px solid #D3D7E0; border-radius: 9px; }
QLabel#noteTagText { font-size: 12px; color: #2A2E37; background: transparent; border: none; }
QToolButton#noteTagRemove { background: transparent; border: none; color: #8A8F99; font-size: 10px; padding: 0 2px; }
QToolButton#noteTagRemove:hover { color: #E53935; }
QLineEdit#noteTagField { background: #FFFFFF; border: 1px dashed #C3C7D0; border-radius: 9px; padding: 1px 8px; font-size: 12px; }
QLineEdit#noteTagField:focus { border: 1px solid #2F6FED; }
QLineEdit#noteTagField[invalid="true"] { border: 1px solid #E53935; }
QFrame#noteBody { background: #FFFFFF; border: 1px solid #E2E4EA; border-radius: 8px; }
QPlainTextEdit#noteEditor, QTextBrowser#noteViewer { background: #FFFFFF; border: none; padding: 10px 14px; font-size: 14px; color: #1B1B1F; }
QFrame#noteFooter { background: #F6F7FA; border: none; border-top: 1px solid #EEF0F4; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px; }
QLabel#noteFooterHint { color: #9095A0; font-size: 11px; }
QToolButton#cheatSheetButton { background: transparent; border: none; padding: 2px; }
QFrame#cheatSheet { background: #FFFFFF; border: 1px solid #D0D4DC; border-radius: 8px; }
QFrame#cheatSheet QLabel { font-size: 13px; color: #1B1B1F; }
QLineEdit#noteSearch { background: #FFFFFF; border: 1px solid #D0D4DC; border-radius: 6px; padding: 6px 8px; color: #1B1B1F; }
QLineEdit#noteSearch:focus { border: 1px solid #2F6FED; }
QLabel#matchesHeader { color: #5A5F6B; font-size: 12px; font-weight: 700; letter-spacing: 0.5px; padding: 2px 2px 0 2px; }
QLabel#toast { background: rgba(34, 37, 43, 225); color: #FFFFFF; border-radius: 10px; padding: 10px 22px; font-size: 14px; font-weight: 600; }
QFrame#findBar { background: #FFFFFF; border: 1px solid #D0D4DC; border-radius: 8px; }
QLineEdit#findField { border: 1px solid #D0D4DC; border-radius: 5px; padding: 3px 6px; }
QLineEdit#findField:focus { border: 1px solid #2F6FED; }
QLineEdit#findField[notFound="true"] { background: #FDECEA; border: 1px solid #E53935; color: #B71C1C; }
QLabel#passwordError { color: #D32F2F; font-size: 12px; }
QLabel#loadingTitle { font-size: 22px; font-weight: 700; color: #22252B; background: transparent; border: none; }
QLabel#loadingMessage { font-size: 14px; color: #6B7080; background: transparent; border: none; }
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


def app_data_folder() -> Path:
    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))


def test_build() -> bool:
    return is_test_build(getattr(sys, "frozen", False), Path(unlimilist.__file__).resolve().parent)


def tasks_folder() -> Path:
    return data_folders.tasks_folder(app_data_folder(), test_build())


def notes_folder() -> Path:
    return data_folders.notes_folder(app_data_folder(), test_build())


def settings_file() -> Path:
    return app_data_folder() / "settings.json"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Unlimilist")  # also names the data folder, so it keeps this spelling
    app.setWindowIcon(app_icon())
    app.setStyle("Fusion")
    app.setPalette(_light_palette())
    app.setStyleSheet(STYLESHEET)

    # The window opens at once; the Tasks and Notes load in the background behind the loading card.
    # Both builds share the settings and the Notebook password; only the Tasks and Notes folders differ.
    window = MainWindow(
        Board(),
        settings_store=SettingsStore(settings_file()),
        test_build=test_build(),
        password=NotebookPassword(KeychainVault()),
    )
    window.show()
    window.load_from(tasks_folder(), notes_folder=notes_folder())
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
