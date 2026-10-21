"""The app's settings file, and the Settings window's Board view tab."""

import json

import pytest

from unlimilist.settings import DEFAULT_CARD_FONT_SIZE, Settings, SettingsStore


def test_without_a_settings_file_the_card_font_size_is_2(tmp_path):
    assert SettingsStore(tmp_path / "settings.json").load() == Settings(card_font_size=2)
    assert DEFAULT_CARD_FONT_SIZE == 2


def test_a_saved_card_font_size_loads_back(tmp_path):
    path = tmp_path / "settings.json"

    SettingsStore(path).save(Settings(card_font_size=4))

    assert json.loads(path.read_text()) == {"card_font_size": 4}
    assert SettingsStore(path).load().card_font_size == 4


@pytest.mark.parametrize("content", ["not json", '{"card_font_size": 9}', '{"card_font_size": "big"}', "[]", '{"card_font_size": true}'])
def test_a_broken_settings_file_means_the_defaults(tmp_path, content):
    path = tmp_path / "settings.json"
    path.write_text(content)

    assert SettingsStore(path).load() == Settings()


def test_saving_creates_the_folder(tmp_path):
    path = tmp_path / "new" / "settings.json"

    SettingsStore(path).save(Settings(card_font_size=5))

    assert SettingsStore(path).load().card_font_size == 5


# The cards' text


def make_card(qtbot, font_size, title="Call grandma about the family recipes", deadline=None, start_passed=False):
    from datetime import date, datetime

    from PySide6.QtGui import QColor

    from unlimilist.domain import Stage, Task, Urgency
    from unlimilist.ui.card import CardWidget

    task = Task(
        id="t",
        title=title,
        stage=Stage.INBOX,
        created_at=datetime(2026, 10, 12, 9, 0),
        details="#family",
        deadline=date(2026, 10, 20) if deadline else None,
        due_date=date(2026, 10, 11) if start_passed else None,
    )
    urgency = Urgency.START_PASSED if start_passed else Urgency.NONE
    card = CardWidget(task, urgency, QColor("#3060C0"), font_size=font_size)
    qtbot.addWidget(card)
    card.resize(300, card.sizeHint().height())
    card.show()
    return card


def test_each_card_font_size_adds_points_to_the_title_dates_and_tag_chip(qtbot):
    normal = make_card(qtbot, 2, deadline=True)
    title, dates, chip = (
        normal.title_label.font().pointSizeF(),
        normal.meta_label.font().pointSizeF(),
        normal.tag_chip.font().pixelSize(),
    )
    assert dates == title - 2

    for size, extra in {1: -2, 2: 0, 3: 2, 4: 5, 5: 7}.items():
        card = make_card(qtbot, size, deadline=True)
        assert card.title_label.font().pointSizeF() == title + extra
        assert card.meta_label.font().pointSizeF() == dates + extra
        assert card.tag_chip.font().pixelSize() == chip + extra


def test_bigger_text_makes_a_card_taller_but_keeps_the_line_limit(qtbot):
    long_title = "Prepare the quarterly report with every number and chart for the board meeting next week"
    heights, lines = [], []
    for size in (1, 2, 3, 4, 5):
        card = make_card(qtbot, size, title=long_title)
        heights.append(card.sizeHint().height())
        lines.append(card.title_label.text().count("\n") + 1)

    assert heights == sorted(heights) and heights[0] < heights[-1]
    assert max(lines) == 4


# The Settings window


@pytest.fixture
def store(tmp_path):
    return SettingsStore(tmp_path / "settings.json")


@pytest.fixture
def window(qtbot, store):
    from datetime import datetime

    from unlimilist.board import Board
    from unlimilist.ui.main_window import MainWindow

    board = Board(clock=lambda: datetime(2026, 10, 12, 9, 0))
    board.add_task("Call grandma", details="#family")
    window = MainWindow(board, settings_store=store)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    return window


def normal_title_points():
    from PySide6.QtWidgets import QLabel

    return QLabel().font().pointSizeF()


def title_points(window):
    return {card.title_label.font().pointSizeF() for card in window.board_view.cards()}


def test_the_board_opens_with_the_saved_card_font_size(qtbot, store):
    store.save(Settings(card_font_size=4))
    from datetime import datetime

    from unlimilist.board import Board
    from unlimilist.ui.main_window import MainWindow

    board = Board(clock=lambda: datetime(2026, 10, 12, 9, 0))
    board.add_task("Call grandma")
    window = MainWindow(board, settings_store=store)
    qtbot.addWidget(window)

    assert title_points(window) == {normal_title_points() + 5}


def test_the_gear_sits_at_the_far_right_of_the_toolbar_with_no_text(window):
    from PySide6.QtGui import QKeySequence

    action = window.settings_action
    button = window.findChild(type(window.toolbar.widgetForAction(action)), "settingsButton")

    assert button is window.toolbar.widgetForAction(action)
    assert action.toolTip() == "Settings" and button.text() == "" and not action.icon().isNull()
    assert window.toolbar.actions()[-1] is action
    assert button.geometry().right() > window.toolbar.width() - 40  # pushed to the far right
    assert action.shortcut() == QKeySequence("Ctrl+,")


def test_the_settings_window_has_board_view_and_notebook_tabs_and_a_close_button(qtbot, store):
    from unlimilist.ui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(Settings())
    qtbot.addWidget(dialog)

    assert [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())] == ["Board view", "Notebook"]
    assert dialog.font_slider.value() == 2
    assert (dialog.font_slider.minimum(), dialog.font_slider.maximum()) == (1, 5)
    dialog.close_button.click()
    assert not dialog.isVisible()


def test_sliding_the_card_font_size_changes_the_board_and_the_preview_at_once_and_saves_it(window, store, monkeypatch):
    from unlimilist.ui.settings_dialog import SettingsDialog

    seen = {}

    def slide(dialog):
        dialog.font_slider.setValue(5)
        seen["board"] = title_points(window)
        seen["preview"] = {card.title_label.font().pointSizeF() for card in dialog.preview_cards()}
        seen["saved"] = store.load().card_font_size
        return 0

    monkeypatch.setattr(SettingsDialog, "exec", slide)
    window.settings_action.trigger()

    big = normal_title_points() + 7
    assert seen == {"board": {big}, "preview": {big}, "saved": 5}
    assert len(window.board_view.cards()) == 1


def test_the_gear_is_off_in_delete_task_mode(window):
    window.delete_action.trigger()
    assert not window.settings_action.isEnabled()

    window.delete_action.trigger()
    assert window.settings_action.isEnabled()


def test_a_dates_line_too_long_for_the_card_ends_in_an_ellipsis(qtbot):
    from PySide6.QtGui import QFontMetrics

    card = make_card(qtbot, 5, title="Book flights", deadline=True, start_passed=True)  # the longest dates line
    card.resize(250, card.height())

    text = card.meta_label.text()
    assert text.startswith("▶ 11/10/2026") and text.endswith("…")
    assert QFontMetrics(card.meta_label.font()).horizontalAdvance(text) <= card.meta_label.width()
