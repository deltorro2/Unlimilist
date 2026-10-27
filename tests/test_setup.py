"""Setup, shown when the app starts with no Vault chosen, and finding the Vault at start (see CONTEXT.md)."""

import pytest
from PySide6.QtWidgets import QDialog

from unlimilist.notebook_password import MemoryVault, NotebookPassword
from unlimilist.settings import Settings, SettingsStore
from unlimilist.ui import setup
from unlimilist.ui.setup import SetupDialog, open_vault
from test_vault import secured_note


@pytest.fixture
def folders(monkeypatch):
    """What the folder chooser answers, in turn (None is Cancel); and every confirmation, recorded."""
    answers, asked = [], []

    def choose(parent, title, start):
        return answers.pop(0) if answers else None

    def confirm_empty(parent, folder, switching=False):
        asked.append(("empty", folder))
        return confirm_empty.answer

    confirm_empty.answer = True
    monkeypatch.setattr(setup, "choose_folder", choose)
    monkeypatch.setattr(setup, "confirm_empty", confirm_empty)
    return answers, asked, confirm_empty


@pytest.fixture
def no_password():
    return NotebookPassword(MemoryVault())


@pytest.fixture
def dialog(qtbot, tmp_path, no_password):
    dialog = SetupDialog(no_password, home=tmp_path)
    qtbot.addWidget(dialog)
    return dialog


def vault_with_data(tmp_path, name="Dropbox Vault"):
    folder = tmp_path / name
    (folder / "tasks").mkdir(parents=True)
    return folder


def test_setup_starts_with_a_welcome(dialog):
    assert dialog.page() == "welcome"
    assert dialog.title.text() == "Welcome to UnlimiList"

    dialog.continue_button.click()

    assert dialog.page() == "vault"
    assert not dialog.continue_button.isEnabled()  # nothing chosen yet
    assert "Dropbox" in dialog.sync_hint.text() and "Google Drive" in dialog.sync_hint.text()


def test_opening_an_existing_vault(dialog, folders, tmp_path):
    answers, asked, _ = folders
    vault = vault_with_data(tmp_path)
    answers.append(vault)
    dialog.continue_button.click()

    dialog.have_vault.click()
    dialog.browse_vault_button.click()

    assert dialog.vault_field.text() == str(vault) and not asked
    dialog.continue_button.click()
    assert dialog.page() == "password"


def test_a_folder_without_tasks_or_notes_is_used_only_once_confirmed(dialog, folders, tmp_path):
    answers, asked, confirm = folders
    empty = tmp_path / "Empty"
    empty.mkdir()
    dialog.continue_button.click()
    dialog.have_vault.click()

    confirm.answer = False  # Choose another… then Cancel
    answers.append(empty)
    dialog.browse_vault_button.click()
    assert asked == [("empty", empty)] and dialog.vault_field.text() == ""

    confirm.answer = True
    answers.append(empty)
    dialog.browse_vault_button.click()
    assert dialog.vault_field.text() == str(empty)


def test_a_new_vault_is_made_in_the_chosen_location_under_its_name(dialog, folders, tmp_path):
    answers, _, _ = folders
    dialog.continue_button.click()
    dialog.new_vault.click()

    assert dialog.location_field.text() == str(tmp_path / "Documents")
    assert dialog.name_field.text() == "UnlimiList Vault"
    answers.append(tmp_path)
    dialog.browse_location_button.click()
    dialog.name_field.setText("Work Vault")
    dialog.continue_button.click()
    dialog.skip_button.click()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.vault() == tmp_path / "Work Vault" and (tmp_path / "Work Vault").is_dir()


def test_a_new_vault_needs_a_plain_name_and_a_location_that_exists(dialog, folders, tmp_path):
    answers, _, _ = folders
    dialog.continue_button.click()
    dialog.new_vault.click()

    dialog.name_field.setText("a/b")
    answers.append(tmp_path)
    dialog.browse_location_button.click()
    dialog.continue_button.click()
    assert dialog.page() == "vault" and "name" in dialog.error.text()

    dialog.name_field.setText("Vault")
    dialog.location_field.setText(str(tmp_path / "gone"))
    dialog.continue_button.click()
    assert dialog.page() == "vault" and "location" in dialog.error.text()


def test_skipping_the_password_finishes_without_one(dialog, folders, tmp_path, no_password):
    folders[0].append(vault_with_data(tmp_path))
    dialog.continue_button.click()
    dialog.have_vault.click()
    dialog.browse_vault_button.click()
    dialog.continue_button.click()

    dialog.skip_button.click()

    assert dialog.result() == QDialog.DialogCode.Accepted and not no_password.exists()


def test_the_password_is_typed_twice_and_kept(dialog, folders, tmp_path, no_password):
    folders[0].append(vault_with_data(tmp_path))
    dialog.continue_button.click()
    dialog.have_vault.click()
    dialog.browse_vault_button.click()
    dialog.continue_button.click()

    dialog.password_field.setText("open sesame")
    dialog.repeat_field.setText("open sesam")
    dialog.continue_button.click()
    assert dialog.page() == "password" and "match" in dialog.error.text()

    dialog.repeat_field.setText("open sesame")
    dialog.continue_button.click()

    assert dialog.result() == QDialog.DialogCode.Accepted and no_password.check("open sesame")


def test_a_vault_with_secured_notes_takes_only_the_password_that_opens_them(dialog, folders, tmp_path, no_password):
    vault = vault_with_data(tmp_path)
    secured_note(vault, "open sesame")
    folders[0].append(vault)
    dialog.continue_button.click()
    dialog.have_vault.click()
    dialog.browse_vault_button.click()
    dialog.continue_button.click()

    assert "Secured Notes" in dialog.password_message.text()
    dialog.password_field.setText("guess")
    dialog.repeat_field.setText("guess")
    dialog.continue_button.click()
    assert dialog.page() == "password" and "doesn't open" in dialog.error.text() and not no_password.exists()

    dialog.password_field.setText("open sesame")
    dialog.repeat_field.setText("open sesame")
    dialog.continue_button.click()
    assert dialog.result() == QDialog.DialogCode.Accepted and no_password.check("open sesame")


def test_with_a_password_on_this_mac_setup_ends_after_the_vault(qtbot, folders, tmp_path):
    password = NotebookPassword(MemoryVault("already here"))
    dialog = SetupDialog(password, home=tmp_path)
    qtbot.addWidget(dialog)
    folders[0].append(vault_with_data(tmp_path))
    dialog.continue_button.click()
    dialog.have_vault.click()
    dialog.browse_vault_button.click()

    assert dialog.continue_button.text() == "Finish"
    dialog.continue_button.click()

    assert dialog.result() == QDialog.DialogCode.Accepted and password.check("already here")


def test_back_returns_to_the_previous_page(dialog):
    dialog.continue_button.click()
    dialog.back_button.click()

    assert dialog.page() == "welcome" and dialog.back_button.isHidden()


# Finding the Vault at start


@pytest.fixture
def store(tmp_path):
    return SettingsStore(tmp_path / "settings.json")


def test_the_saved_vault_opens_with_no_questions(store, no_password, tmp_path, monkeypatch):
    vault = vault_with_data(tmp_path)
    store.save(Settings(vault=str(vault)))
    monkeypatch.setattr(SetupDialog, "exec", lambda self: pytest.fail("Setup shown"))

    assert open_vault(store, no_password) == vault


def test_with_no_vault_setup_runs_and_its_choice_is_saved(store, no_password, tmp_path, folders, monkeypatch):
    vault = vault_with_data(tmp_path)
    store.save(Settings(card_font_size=4))
    folders[0].append(vault)

    def run(dialog):
        dialog.continue_button.click()
        dialog.have_vault.click()
        dialog.browse_vault_button.click()
        dialog.continue_button.click()
        dialog.skip_button.click()
        return dialog.result()

    monkeypatch.setattr(SetupDialog, "exec", run)

    assert open_vault(store, no_password) == vault
    assert store.load() == Settings(card_font_size=4, vault=str(vault))


def test_closing_setup_quits_and_saves_nothing(store, no_password, monkeypatch):
    monkeypatch.setattr(SetupDialog, "exec", lambda self: QDialog.DialogCode.Rejected)

    assert open_vault(store, no_password) is None
    assert store.load().vault is None


def test_a_missing_vault_can_be_tried_again(store, no_password, tmp_path, monkeypatch):
    vault = tmp_path / "Drive" / "Vault"
    store.save(Settings(vault=str(vault)))
    asked = []

    def missing(parent, folder):
        asked.append(folder)
        vault.mkdir(parents=True)  # the drive was plugged in
        return "retry"

    monkeypatch.setattr(setup, "vault_missing", missing)

    assert open_vault(store, no_password) == vault and asked == [vault]
    assert not (tmp_path / "Drive" / "Vault" / "tasks").exists()  # never made by the app on its own


def test_a_missing_vault_can_be_replaced_by_another(store, no_password, tmp_path, folders, monkeypatch):
    store.save(Settings(vault=str(tmp_path / "gone")))
    other = vault_with_data(tmp_path, "Other")
    folders[0].append(other)
    monkeypatch.setattr(setup, "vault_missing", lambda parent, folder: "choose")

    assert open_vault(store, no_password) == other
    assert store.load().vault == str(other)


def test_quitting_at_a_missing_vault_keeps_it_saved(store, no_password, tmp_path, monkeypatch):
    store.save(Settings(vault=str(tmp_path / "gone")))
    monkeypatch.setattr(setup, "vault_missing", lambda parent, folder: "quit")

    assert open_vault(store, no_password) is None
    assert store.load().vault == str(tmp_path / "gone")
