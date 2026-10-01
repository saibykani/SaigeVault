"""Authenticated encryption for secrets at rest (OAuth tokens).

AES-256-GCM. Ciphertext layout: version (1 byte) | nonce (12 bytes) | ciphertext+tag.
Associated data binds each ciphertext to its owner row and field, so a token
copied into another user's row (or another column) fails to decrypt.

Key rotation: add the new key under a higher version, keep old versions for
decryption, re-encrypt lazily on next write.
"""

from __future__ import annotations

import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12
KEY_BYTES = 32


class DecryptionError(Exception):
    """Ciphertext is corrupt, tampered, bound to other data, or the key is unknown."""


def decode_key(encoded: str) -> bytes:
    try:
        key = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (binascii.Error, ValueError) as exc:
        raise ValueError("TOKEN_ENCRYPTION_KEY must be url-safe base64") from exc
    if len(key) != KEY_BYTES:
        raise ValueError("TOKEN_ENCRYPTION_KEY must decode to exactly 32 bytes")
    return key


def generate_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(KEY_BYTES)).decode()


class TokenCipher:
    def __init__(self, keys: dict[int, bytes], current_version: int) -> None:
        if current_version not in keys:
            raise ValueError("current key version missing")
        if not 1 <= current_version <= 255:
            raise ValueError("key version must fit in one byte")
        self._keys = {v: AESGCM(k) for v, k in keys.items()}
        self._current = current_version

    @classmethod
    def from_single_key(cls, encoded: str) -> TokenCipher:
        return cls({1: decode_key(encoded)}, current_version=1)

    @property
    def current_version(self) -> int:
        return self._current

    def encrypt(self, plaintext: str, *, associated_data: str) -> bytes:
        nonce = os.urandom(NONCE_BYTES)
        sealed = self._keys[self._current].encrypt(
            nonce, plaintext.encode(), associated_data.encode()
        )
        return bytes([self._current]) + nonce + sealed

    def decrypt(self, blob: bytes, *, associated_data: str) -> str:
        if len(blob) < 1 + NONCE_BYTES + 16:
            raise DecryptionError("ciphertext too short")
        aead = self._keys.get(blob[0])
        if aead is None:
            raise DecryptionError("unknown key version")
        nonce, sealed = blob[1 : 1 + NONCE_BYTES], blob[1 + NONCE_BYTES :]
        try:
            return aead.decrypt(nonce, sealed, associated_data.encode()).decode()
        except InvalidTag as exc:
            raise DecryptionError("authentication failed") from exc
