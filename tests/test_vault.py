"""The Vault: the folder holding the Tasks and Notes, chosen in Setup or in Settings → My Vault (see CONTEXT.md)."""

import json
from datetime import datetime

import pytest

from unlimilist.notebook import Note, NoteType
from unlimilist.note_store import MarkdownNoteStore
from unlimilist.secure import encrypt
from unlimilist.settings import Settings, SettingsStore
from unlimilist.vault import has_data, has_secured_notes, new_vault_folder, notes_folder, password_opens, tasks_folder


def secured_note(vault, password="open sesame"):
    MarkdownNoteStore(notes_folder(vault)).save(
        Note(
            id="n1",
            title="Bank",
            body=encrypt("PIN 1234", password),
            note_type=NoteType.SECURED,
            tags=(),
            created_at=datetime(2026, 10, 1, 9, 0),
        )
    )


def test_a_vault_keeps_tasks_and_notes_in_their_own_folders(tmp_path):
    assert tasks_folder(tmp_path) == tmp_path / "tasks"
    assert notes_folder(tmp_path) == tmp_path / "notes"


def test_a_folder_with_tasks_or_notes_has_data(tmp_path):
    assert not has_data(tmp_path)
    (tmp_path / "other.txt").write_text("not ours")
    assert not has_data(tmp_path)

    (tmp_path / "notes").mkdir()

    assert has_data(tmp_path)


def test_a_new_vault_is_the_named_folder_inside_the_location(tmp_path):
    assert new_vault_folder(tmp_path, "  UnlimiList Vault ") == tmp_path / "UnlimiList Vault"


@pytest.mark.parametrize("name", ["", "   ", "a/b", ".", ".."])
def test_a_vault_name_must_be_a_plain_folder_name(tmp_path, name):
    with pytest.raises(ValueError):
        new_vault_folder(tmp_path, name)


def test_any_password_opens_a_vault_without_secured_notes(tmp_path):
    assert not has_secured_notes(tmp_path)
    assert password_opens(tmp_path, "anything")


def test_a_vault_with_secured_notes_opens_only_with_their_password(tmp_path):
    secured_note(tmp_path)

    assert has_secured_notes(tmp_path)
    assert password_opens(tmp_path, "open sesame")
    assert not password_opens(tmp_path, "wrong")


# Where the Vault is remembered


def test_without_a_vault_in_settings_none_is_chosen(tmp_path):
    assert SettingsStore(tmp_path / "settings.json").load().vault is None


def test_the_vault_is_kept_in_settings_as_a_full_path(tmp_path):
    path = tmp_path / "settings.json"
    vault = tmp_path / "Dropbox" / "UnlimiList Vault"

    SettingsStore(path).save(Settings(vault=str(vault)))

    assert json.loads(path.read_text())["vault"] == str(vault)
    assert SettingsStore(path).load().vault == str(vault)


@pytest.mark.parametrize("value", ["", 7, ["a"], None, "relative/folder"])
def test_an_odd_vault_in_settings_means_none_is_chosen(tmp_path, value):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"card_font_size": 3, "vault": value}))

    settings = SettingsStore(path).load()

    assert settings.vault is None and settings.card_font_size == 3


# Settings → My Vault


def task_titles(window):
    return {card.task.title for card in window.board_view.cards()}


@pytest.fixture
def two_vaults(tmp_path):
    from unlimilist.board import Board
    from unlimilist.store import MarkdownTaskStore

    first, second = tmp_path / "First", tmp_path / "Second"
    Board(MarkdownTaskStore(tasks_folder(first))).add_task("From the first Vault")
    Board(MarkdownTaskStore(tasks_folder(second))).add_task("From the second Vault")
    return first, second


@pytest.fixture
def window(qtbot, tmp_path, two_vaults):
    from unlimilist.board import Board
    from unlimilist.ui.main_window import MainWindow

    first, _ = two_vaults
    store = SettingsStore(tmp_path / "settings.json")
    store.save(Settings(vault=str(first)))
    window = MainWindow(Board(), settings_store=store, vault=first)
    qtbot.addWidget(window)
    window.show()
    window.load_from(tasks_folder(first), minimum_ms=0, notes_folder=notes_folder(first))
    qtbot.waitUntil(lambda: window.loading_screen is None, timeout=5000)
    assert task_titles(window) == {"From the first Vault"}
    window.store = store
    return window


def test_my_vault_shows_where_the_vault_is(qtbot, tmp_path):
    from unlimilist.ui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(Settings(), vault=tmp_path / "Vault")
    qtbot.addWidget(dialog)

    assert [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())][-1] == "My Vault"
    assert dialog.vault_path.text() == str(tmp_path / "Vault")


def test_the_test_build_has_no_my_vault_tab(qtbot):
    from unlimilist.ui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(Settings())
    qtbot.addWidget(dialog)

    assert "My Vault" not in [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]


def change_vault(monkeypatch, window, folder, switch=True):
    from unlimilist.ui import setup
    from unlimilist.ui.settings_dialog import SettingsDialog

    monkeypatch.setattr(setup, "choose_folder", lambda parent, title, start: folder)
    monkeypatch.setattr(setup, "confirm_switch", lambda parent, chosen: switch)

    def run(dialog):
        dialog.change_vault_button.click()
        return dialog.result()

    monkeypatch.setattr(SettingsDialog, "exec", run)
    window.settings_action.trigger()


def test_changing_the_vault_reloads_the_board_from_it_and_remembers_it(qtbot, monkeypatch, window, two_vaults):
    _, second = two_vaults
    window.toggle_tag("nothing")

    change_vault(monkeypatch, window, second)

    qtbot.waitUntil(lambda: window.loading_screen is None, timeout=5000)
    assert task_titles(window) == {"From the second Vault"}
    assert window.store.load().vault == str(second)
    assert window.vault() == second
    assert window._tag_filter == frozenset()


def test_cancelling_the_switch_keeps_the_vault(qtbot, monkeypatch, window, two_vaults):
    first, second = two_vaults

    change_vault(monkeypatch, window, second, switch=False)

    assert window.loading_screen is None and task_titles(window) == {"From the first Vault"}
    assert window.store.load().vault == str(first)


def test_choosing_the_same_vault_changes_nothing(qtbot, monkeypatch, window, two_vaults):
    first, _ = two_vaults

    change_vault(monkeypatch, window, first)

    assert window.loading_screen is None and window.store.load().vault == str(first)
