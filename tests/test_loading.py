"""Startup: the window opens at once with a loading card while the Tasks load in the background."""

import threading
import time
from datetime import datetime

import pytest

from unlimilist.board import Board
from unlimilist.domain import Stage, Task
from unlimilist.store import MarkdownTaskStore
from unlimilist.ui import loading
from unlimilist.ui.main_window import MainWindow


@pytest.fixture
def task_folder(tmp_path):
    store = MarkdownTaskStore(tmp_path)
    store.save(Task(id="t1", title="Plan", stage=Stage.INBOX, created_at=datetime(2026, 10, 1), details="#home"))
    store.save(Task(id="t2", title="Ship", stage=Stage.IN_PROCESS, created_at=datetime(2026, 10, 2)))
    return tmp_path


@pytest.fixture
def window(qtbot):
    window = MainWindow(Board())
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    return window


def titles(window, stage):
    # The test screen is narrow, so a title may wrap; compare it as one line.
    return [" ".join(card.title_label.text().split()) for card in window.board_view.column_widget(stage).cards()]


def loaded(window):
    return window.loading_screen is None


def test_the_window_opens_at_once_with_a_loading_card_over_a_faded_outline(window, task_folder):
    window.load_from(task_folder, minimum_ms=200)

    screen = window.loading_screen
    assert screen.isVisible()
    assert (screen.title(), screen.message()) == ("Getting things ready", "Preparing your workspace…")
    assert screen.geometry() == window.rect()  # it covers, and fades, the whole window
    for stage in Stage:
        column = window.board_view.column_widget(stage)
        assert column.placeholder_count() > 0
        assert column.cards() == []
    assert not window.new_task_action.isEnabled()
    assert not window.delete_action.isEnabled()


def test_once_loading_ends_the_card_goes_and_the_board_fills_in(qtbot, window, task_folder):
    window.load_from(task_folder, minimum_ms=200)

    qtbot.waitUntil(lambda: loaded(window), timeout=5000)

    assert titles(window, Stage.INBOX) == ["1. Plan"]
    assert titles(window, Stage.IN_PROCESS) == ["1. Ship"]
    assert all(window.board_view.column_widget(s).placeholder_count() == 0 for s in Stage)
    assert [b.tag for b in window.sidebar.tag_bubbles()] == ["home"]
    assert window.new_task_action.isEnabled() and window.delete_action.isEnabled()


def test_the_card_stays_for_the_minimum_time_even_when_loading_is_quick(qtbot, window, task_folder):
    started = time.monotonic()
    window.load_from(task_folder, minimum_ms=800)

    qtbot.waitUntil(lambda: loaded(window), timeout=5000)

    assert time.monotonic() - started >= 0.8


def test_the_tasks_load_off_the_ui_thread_so_the_progress_bar_keeps_moving(qtbot, window, task_folder, monkeypatch):
    open_board = loading.open_board
    threads = []

    def slow_open_board(folder):
        threads.append(threading.current_thread())
        time.sleep(0.6)
        return open_board(folder)

    monkeypatch.setattr(loading, "open_board", slow_open_board)
    window.load_from(task_folder, minimum_ms=0)
    phases = set()
    qtbot.waitUntil(lambda: phases.add(window.loading_screen.bar_phase()) or len(phases) > 3, timeout=3000)

    qtbot.waitUntil(lambda: loaded(window), timeout=5000)
    assert threads and threads[0] is not threading.main_thread()


def test_files_that_cannot_be_read_are_reported_once_loaded(qtbot, window, task_folder):
    (task_folder / "broken.md").write_text("no front matter", encoding="utf-8")

    window.load_from(task_folder, minimum_ms=0)
    qtbot.waitUntil(lambda: loaded(window), timeout=5000)

    assert window.statusBar().currentMessage().startswith("1 file(s) could not be read")


def test_the_notes_load_with_the_tasks_and_broken_note_files_are_reported_too(qtbot, window, task_folder, tmp_path):
    from unlimilist.note_store import MarkdownNoteStore
    from unlimilist.notebook import Notebook

    notes = tmp_path / "notes"
    Notebook(MarkdownNoteStore(notes)).create("Lisbon", "Day 1")
    (notes / "broken.md").write_text("no front matter", encoding="utf-8")

    window.load_from(task_folder, minimum_ms=0, notes_folder=notes)
    qtbot.waitUntil(lambda: loaded(window), timeout=5000)

    window.show_notebook()
    assert [window.notebook_view.row_texts(i)[0] for i in window.notebook_view.shown_ids()] == ["Lisbon"]
    assert window.statusBar().currentMessage().startswith("1 file(s) could not be read")


def test_if_the_data_folder_cannot_be_read_the_card_says_so_and_stays(qtbot, window, tmp_path):
    not_a_folder = tmp_path / "tasks"
    not_a_folder.write_text("a file where the folder should be", encoding="utf-8")

    window.load_from(not_a_folder, minimum_ms=0)
    qtbot.waitUntil(lambda: window.loading_screen.message().startswith("Couldn't open your Tasks"), timeout=5000)
    qtbot.wait(300)

    assert not loaded(window)
    assert window.loading_screen.isVisible()
