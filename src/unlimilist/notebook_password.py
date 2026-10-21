"""The Notebook password: one password for every Secured Note. Its only copy outside your head is in the macOS
Keychain (never in the app's files). Once typed it is remembered until the app quits."""

import hmac
from collections.abc import Callable
from typing import Protocol

_SERVICE = "Unlimilist"  # the real app and the test build share this Keychain entry
_ACCOUNT = "Notebook password"


class Vault(Protocol):
    def get(self) -> str | None: ...

    def set(self, password: str) -> None: ...


class KeychainVault:
    """The login Keychain, through keyring (the Windows Credential Manager on Windows)."""

    def get(self) -> str | None:
        import keyring

        return keyring.get_password(_SERVICE, _ACCOUNT)

    def set(self, password: str) -> None:
        import keyring

        keyring.set_password(_SERVICE, _ACCOUNT, password)


class MemoryVault:
    def __init__(self, password: str | None = None):
        self._password = password

    def get(self) -> str | None:
        return self._password

    def set(self, password: str) -> None:
        self._password = password


class NotebookPassword:
    def __init__(self, vault: Vault):
        self._vault = vault
        self._password: str | None = None  # this session's, once typed

    def exists(self) -> bool:
        return self._vault.get() is not None

    def is_unlocked(self) -> bool:
        return self._password is not None

    def current(self) -> str | None:
        return self._password

    def check(self, typed: str) -> bool:
        """Whether `typed` is the password, without unlocking anything."""
        stored = self._vault.get()
        return stored is not None and hmac.compare_digest(typed.encode("utf-8"), stored.encode("utf-8"))

    def unlock(self, typed: str, opens: Callable[[str], bool] | None = None) -> bool:
        """Remember `typed` for the session if it is the password. With no Keychain copy (say it was deleted by
        hand), a password that `opens` the Note being opened is accepted, and stored again."""
        if self.check(typed):
            self._password = typed
            return True
        if not self.exists() and opens is not None and opens(typed):
            self.create(typed)
            return True
        return False

    def create(self, password: str) -> None:
        self._vault.set(password)
        self._password = password
