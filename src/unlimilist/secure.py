"""Encrypts a Secured Note's Body with the Notebook password: AES-256-GCM, the key derived with scrypt.

The block is plain text, so the Note's file stays a readable Markdown file around it:

    -----BEGIN UNLIMILIST SECURED NOTE-----
    <base64 of version, salt, nonce and ciphertext, 76 characters a line>
    -----END UNLIMILIST SECURED NOTE-----
"""

import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

_BEGIN = "-----BEGIN UNLIMILIST SECURED NOTE-----"
_END = "-----END UNLIMILIST SECURED NOTE-----"
_VERSION = b"\x01"
_SALT_BYTES = 16
_NONCE_BYTES = 12
_LINE = 76


class WrongPassword(Exception):
    """The password does not open this block (or the block is damaged)."""


def _key(password: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode("utf-8"))


def encrypt(text: str, password: str) -> str:
    salt, nonce = os.urandom(_SALT_BYTES), os.urandom(_NONCE_BYTES)
    sealed = AESGCM(_key(password, salt)).encrypt(nonce, text.encode("utf-8"), None)
    encoded = base64.b64encode(_VERSION + salt + nonce + sealed).decode("ascii")
    lines = [encoded[i : i + _LINE] for i in range(0, len(encoded), _LINE)]
    return "\n".join([_BEGIN, *lines, _END])


def decrypt(block: str, password: str) -> str:
    lines = [line.strip() for line in block.strip().splitlines()]
    if len(lines) < 3 or lines[0] != _BEGIN or lines[-1] != _END:
        raise WrongPassword("not a secured block")
    try:
        raw = base64.b64decode("".join(lines[1:-1]), validate=True)
    except binascii.Error as error:
        raise WrongPassword("damaged block") from error
    if raw[:1] != _VERSION:
        raise WrongPassword("unknown block version")
    salt = raw[1 : 1 + _SALT_BYTES]
    nonce = raw[1 + _SALT_BYTES : 1 + _SALT_BYTES + _NONCE_BYTES]
    sealed = raw[1 + _SALT_BYTES + _NONCE_BYTES :]
    try:
        return AESGCM(_key(password, salt)).decrypt(nonce, sealed, None).decode("utf-8")
    except (InvalidTag, ValueError) as error:
        raise WrongPassword("wrong password") from error
