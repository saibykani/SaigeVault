from __future__ import annotations

import pytest

from saige_api.crypto import DecryptionError, TokenCipher, decode_key, generate_key


def cipher() -> TokenCipher:
    return TokenCipher.from_single_key(generate_key())


def test_round_trip() -> None:
    c = cipher()
    blob = c.encrypt("1//refresh-token", associated_data="conn-1:refresh")
    assert b"refresh-token" not in blob
    assert c.decrypt(blob, associated_data="conn-1:refresh") == "1//refresh-token"


def test_nonce_makes_ciphertexts_unique() -> None:
    c = cipher()
    assert c.encrypt("same", associated_data="a") != c.encrypt("same", associated_data="a")


def test_ciphertext_bound_to_associated_data() -> None:
    c = cipher()
    blob = c.encrypt("token", associated_data="conn-1:refresh")
    with pytest.raises(DecryptionError):
        c.decrypt(blob, associated_data="conn-2:refresh")  # moved to another row
    with pytest.raises(DecryptionError):
        c.decrypt(blob, associated_data="conn-1:access")  # moved to another column


def test_tampering_detected() -> None:
    c = cipher()
    blob = bytearray(c.encrypt("token", associated_data="x"))
    blob[-1] ^= 0x01
    with pytest.raises(DecryptionError):
        c.decrypt(bytes(blob), associated_data="x")


def test_wrong_key_and_unknown_version() -> None:
    blob = cipher().encrypt("token", associated_data="x")
    with pytest.raises(DecryptionError):
        cipher().decrypt(blob, associated_data="x")
    with pytest.raises(DecryptionError):
        cipher().decrypt(bytes([9]) + blob[1:], associated_data="x")


def test_key_rotation_reads_old_versions() -> None:
    old, new = decode_key(generate_key()), decode_key(generate_key())
    v1 = TokenCipher({1: old}, current_version=1)
    blob = v1.encrypt("token", associated_data="x")
    rotated = TokenCipher({1: old, 2: new}, current_version=2)
    assert rotated.decrypt(blob, associated_data="x") == "token"
    assert rotated.encrypt("token", associated_data="x")[0] == 2


@pytest.mark.parametrize("bad", ["", "not-base64!!", "c2hvcnQ"])
def test_invalid_keys_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match="TOKEN_ENCRYPTION_KEY"):
        decode_key(bad)
