"""Secured Notes: the Body is encrypted with the Notebook password, which is checked against the Keychain copy."""

import pytest

from unlimilist.notebook_password import MemoryVault, NotebookPassword
from unlimilist.secure import WrongPassword, decrypt, encrypt


def test_an_encrypted_body_reads_back_only_with_its_password():
    block = encrypt("# Bank\nPIN 1234", "correct horse")

    assert "1234" not in block
    assert decrypt(block, "correct horse") == "# Bank\nPIN 1234"
    with pytest.raises(WrongPassword):
        decrypt(block, "wrong")


def test_the_same_body_encrypts_differently_each_time():
    assert encrypt("same", "pw") != encrypt("same", "pw")


def test_a_damaged_block_is_refused_like_a_wrong_password():
    block = encrypt("text", "pw")
    damaged = block.replace(block.splitlines()[1][:8], "AAAAAAAA", 1)

    with pytest.raises(WrongPassword):
        decrypt(damaged, "pw")


def test_there_is_no_password_until_one_is_created_and_then_it_is_kept_in_the_vault():
    vault = MemoryVault()
    password = NotebookPassword(vault)

    assert not password.exists()
    password.create("s3cret")

    assert vault.get() == "s3cret"
    assert password.exists()
    assert password.is_unlocked()  # creating it unlocks the session


def test_typing_the_password_unlocks_the_session_and_a_wrong_one_does_not():
    password = NotebookPassword(MemoryVault("s3cret"))

    assert not password.is_unlocked()
    assert not password.unlock("nope")
    assert not password.is_unlocked()
    assert password.unlock("s3cret")
    assert password.is_unlocked()
    assert password.current() == "s3cret"


def test_without_a_keychain_copy_a_password_that_opens_the_note_is_accepted_and_stored():
    vault = MemoryVault()
    password = NotebookPassword(vault)

    assert not password.unlock("s3cret", opens=lambda typed: False)
    assert password.unlock("s3cret", opens=lambda typed: typed == "s3cret")
    assert vault.get() == "s3cret"


def test_check_compares_with_the_vault_without_unlocking():
    password = NotebookPassword(MemoryVault("s3cret"))

    assert password.check("s3cret")
    assert not password.check("other")
    assert not password.is_unlocked()


# The dialogs


def _answer(qtbot, steps):
    """Fill in the open password dialog and press OK, once per step (a list of field values)."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    seen = []

    def act():
        dialog = QApplication.activeModalWidget()
        if dialog is None:
            QTimer.singleShot(20, act)
            return
        values = steps.pop(0)
        for field, value in zip(dialog.fields, values):
            field.setText(value)
        dialog.buttons.button(dialog.buttons.StandardButton.Ok).click()
        seen.append(dialog.error.text() if not dialog.error.isHidden() else "")
        if steps:
            QTimer.singleShot(20, act)

    QTimer.singleShot(20, act)
    return seen


def test_asking_keeps_the_dialog_open_until_the_password_is_right(qtbot):
    from unlimilist.ui.password_dialogs import ask_password

    seen = _answer(qtbot, [["nope"], ["s3cret"]])

    assert ask_password(None, lambda typed: typed == "s3cret") == "s3cret"
    assert seen[0] == "Wrong password. Try again."


def test_a_new_password_must_be_typed_twice_the_same(qtbot):
    from unlimilist.ui.password_dialogs import create_password

    seen = _answer(qtbot, [["", ""], ["one", "two"], ["same", "same"]])

    assert create_password(None) == "same"
    assert seen[:2] == ["The password can't be empty.", "The two passwords don't match."]


def test_changing_needs_the_current_password(qtbot):
    from unlimilist.ui.password_dialogs import change_password

    seen = _answer(qtbot, [["bad", "n3w", "n3w"], ["old", "n3w", "n3w"]])

    assert change_password(None, lambda typed: typed == "old") == ("old", "n3w")
    assert seen[0] == "The current password is wrong."
