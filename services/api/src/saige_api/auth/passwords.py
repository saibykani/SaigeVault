"""Password hashing and policy.

- Argon2id (OWASP-recommended parameters); hashes are upgraded on sign-in
  when the parameters change.
- No length or composition rules. Passwords known from breaches are
  rejected (k-anonymity: only 5 hex chars of the SHA-1 leave the server).
- Verification against a fixed dummy hash for unknown accounts keeps response
  times the same whether or not the email exists.
"""

from __future__ import annotations

import hashlib
import unicodedata

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from saige_api.core.errors import AppError
from saige_api.core.logging import get_logger

logger = get_logger("saige_api.auth.passwords")

# No minimum length (owner's choice). A generous cap only protects the server:
# hashing unbounded input is a denial-of-service vector.
MAX_LENGTH = 1024
PWNED_RANGE_URL = "https://api.pwnedpasswords.com/range/"

# OWASP 2025 Argon2id baseline: m=19 MiB, t=2, p=1.
_hasher = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1)
_DUMMY_HASH = _hasher.hash("saige-dummy-password-for-timing")

_COMMON = frozenset(
    {
        "password1234",
        "passwordpassword",
        "123456789012",
        "qwertyuiopas",
        "iloveyou1234",
        "letmein12345",
        "welcome12345",
        "adminadmin12",
        "saigevault123",
        "changeme1234",
    }
)


class WeakPasswordError(AppError):
    code = "weak_password"


def normalize(password: str) -> str:
    # NFKC so the same password typed on different keyboards/OSes matches.
    return unicodedata.normalize("NFKC", password)


def hash_password(password: str) -> str:
    return _hasher.hash(normalize(password))


def verify_password(stored_hash: str | None, password: str) -> bool:
    """Constant-work verification; `stored_hash=None` means no such account."""
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, normalize(password)) and bool(stored_hash)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


def check_policy(password: str, *, email: str) -> None:
    """Raise WeakPasswordError with a user-facing reason."""
    value = normalize(password)
    if not value:
        raise WeakPasswordError("Enter a password.")
    if len(value) > MAX_LENGTH:
        raise WeakPasswordError(f"Use at most {MAX_LENGTH} characters.")
    if value.lower() in _COMMON:
        raise WeakPasswordError("That password is too easy to guess.")


async def is_breached(http: httpx.AsyncClient, password: str) -> bool:
    """Have I Been Pwned range query. Fails open: an outage must not block sign-up."""
    digest = hashlib.sha1(normalize(password).encode(), usedforsecurity=False).hexdigest().upper()
    prefix, suffix = digest[:5], digest[5:]
    try:
        response = await http.get(
            PWNED_RANGE_URL + prefix,
            headers={"Add-Padding": "true", "User-Agent": "saige-vault"},
            timeout=3.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("breach_check_unavailable", error=type(exc).__name__)
        return False
    for line in response.text.splitlines():
        candidate, _, count = line.partition(":")
        if candidate.strip() == suffix and count.strip() not in {"", "0"}:
            return True
    return False
