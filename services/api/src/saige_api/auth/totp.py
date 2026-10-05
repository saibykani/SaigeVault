"""Time-based one-time passwords (RFC 6238) and recovery codes.

Compatible with Google Authenticator, Microsoft Authenticator, 1Password,
Authy and similar apps: SHA-1, 6 digits, 30-second steps.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote, urlencode

DIGITS = 6
STEP_SECONDS = 30
# Accept the previous and next step to tolerate clock drift on phones.
DRIFT_STEPS = 1
RECOVERY_CODE_COUNT = 10


def new_secret() -> str:
    """160-bit secret, base32 without padding (what authenticator apps expect)."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _code_at(secret: str, step: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    mac = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    value = struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**DIGITS).zfill(DIGITS)


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // STEP_SECONDS)


def code_at(secret: str, now: float | None = None) -> str:
    return _code_at(secret, current_step(now))


def verify(secret: str, code: str, *, last_used_step: int | None, now: float | None = None) -> int:
    """Return the matched time step, or -1.

    Steps at or before `last_used_step` are refused, so an intercepted code
    cannot be replayed within its validity window.
    """
    candidate = "".join(code.split())
    if len(candidate) != DIGITS or not candidate.isdigit():
        return -1
    step = current_step(now)
    for offset in range(-DRIFT_STEPS, DRIFT_STEPS + 1):
        s = step + offset
        if last_used_step is not None and s <= last_used_step:
            continue
        if hmac.compare_digest(_code_at(secret, s), candidate):
            return s
    return -1


def provisioning_uri(secret: str, *, account: str, issuer: str = "Saige Vault") -> str:
    label = quote(f"{issuer}:{account}")
    params = urlencode(
        {"secret": secret, "issuer": issuer, "digits": DIGITS, "period": STEP_SECONDS}
    )
    return f"otpauth://totp/{label}?{params}"


def new_recovery_codes() -> list[str]:
    """Ten single-use codes like `k7m2-9xqp-4tzr` (~60 bits each)."""
    alphabet = "23456789abcdefghjkmnpqrstuvwxyz"
    return [
        "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3))
        for _ in range(RECOVERY_CODE_COUNT)
    ]


def hash_recovery_code(code: str) -> str:
    # High-entropy random codes: a fast hash is sufficient.
    return hashlib.sha256("".join(code.lower().split()).replace("-", "").encode()).hexdigest()
