"""Email + password accounts with an optional TOTP second factor.

The credential lives on the user document as `password`:
{hash, changed_at, totp_secret (encrypted), totp_key_version, totp_enabled_at,
 totp_last_step, recovery_hashes}
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from typing import Any

from pymongo.errors import DuplicateKeyError

from saige_api.auth import passwords, totp
from saige_api.auth.users import find_user_by_email, new_user
from saige_api.core.errors import AppError, ConflictError, RateLimitedError, UnauthorizedError
from saige_api.crypto import TokenCipher
from saige_api.db import Doc, now
from saige_api.enums import UserStatus
from saige_api.kv import KeyValueStore

# Per-account brute-force protection, independent of the per-IP limit.
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60
MFA_TICKET_SECONDS = 5 * 60
MFA_MAX_ATTEMPTS = 5

INVALID_CREDENTIALS = "Email or password is incorrect."
_CONFLICT = (
    "An account with this email already exists. Sign in instead, or use "
    "Continue with Google if that's how you joined."
)


class InvalidCredentialsError(UnauthorizedError):
    code = "invalid_credentials"


class InvalidCodeError(AppError):
    # 400, not 401: a mistyped code must not look like an expired session.
    code = "invalid_code"


class IncorrectPasswordError(AppError):
    """Wrong current password during a signed-in, sensitive change."""

    code = "incorrect_password"


class TwoFactorUnavailableError(AppError):
    status_code = 503
    code = "two_factor_unavailable"


def _email_key(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


def _totp_aad(user_id: uuid.UUID) -> str:
    return f"user:{user_id}:totp"


def new_credential(password: str) -> dict[str, Any]:
    return {
        "hash": passwords.hash_password(password),
        "changed_at": now(),
        "totp_secret": None,
        "totp_key_version": None,
        "totp_enabled_at": None,
        "totp_last_step": None,
        "recovery_hashes": [],
    }


@dataclass(frozen=True, slots=True)
class LoginResult:
    user: Doc
    mfa_ticket: str | None = None


class PasswordAccountService:
    def __init__(self, db: Any, kv: KeyValueStore, cipher: TokenCipher | None) -> None:
        self._db = db
        self._kv = kv
        self._cipher = cipher

    async def _user(self, user_id: uuid.UUID) -> Doc | None:
        raw = await self._db.users.find_one({"_id": user_id})
        return Doc(raw) if raw else None

    async def credential_for(self, user_id: uuid.UUID) -> dict[str, Any] | None:
        user = await self._user(user_id)
        return user.password if user else None

    # -- registration ---------------------------------------------------------

    async def register(self, email: str, password: str, display_name: str | None) -> Doc:
        if await find_user_by_email(self._db, email) is not None:
            raise ConflictError(_CONFLICT)
        user = new_user(email, display_name)
        user["password"] = new_credential(password)
        user["last_login_at"] = now()
        try:
            await self._db.users.insert_one(user)
        except DuplicateKeyError as exc:
            raise ConflictError(_CONFLICT) from exc
        return Doc(user)

    # -- sign-in --------------------------------------------------------------

    async def _check_lockout(self, email: str) -> str:
        key = f"saige:login_fail:{_email_key(email)}"
        raw = await self._kv.get(key)
        if raw is not None and int(raw) >= MAX_FAILED_ATTEMPTS:
            raise RateLimitedError(
                "Too many failed attempts for this account. Try again in 15 minutes."
            )
        return key

    async def authenticate(self, email: str, password: str) -> LoginResult:
        fail_key = await self._check_lockout(email)
        user = await find_user_by_email(self._db, email)
        credential = user.password if user else None
        # Always run one Argon2 verification so timing doesn't reveal accounts.
        ok = passwords.verify_password(credential["hash"] if credential else None, password)
        if not ok or user is None or credential is None:
            await self._kv.incr(fail_key, ttl_seconds=LOCKOUT_SECONDS)
            raise InvalidCredentialsError(INVALID_CREDENTIALS)
        if user.deleted_at is not None or user.status != UserStatus.ACTIVE.value:
            raise InvalidCredentialsError(INVALID_CREDENTIALS)
        await self._kv.pop(fail_key)
        updates: dict[str, Any] = {}
        if passwords.needs_rehash(credential["hash"]):
            updates["password.hash"] = passwords.hash_password(password)
        if credential.get("totp_enabled_at") is not None:
            if updates:
                await self._db.users.update_one({"_id": user.id}, {"$set": updates})
            return LoginResult(user=user, mfa_ticket=await self._issue_mfa_ticket(user.id))
        updates["last_login_at"] = now()
        await self._db.users.update_one({"_id": user.id}, {"$set": updates})
        return LoginResult(user=user)

    async def _issue_mfa_ticket(self, user_id: uuid.UUID) -> str:
        ticket = secrets.token_urlsafe(32)
        await self._kv.set(
            f"saige:mfa:{hashlib.sha256(ticket.encode()).hexdigest()}",
            str(user_id),
            ttl_seconds=MFA_TICKET_SECONDS,
        )
        return ticket

    async def complete_mfa(self, ticket: str, code: str) -> Doc:
        digest = hashlib.sha256(ticket.encode()).hexdigest()
        ticket_key = f"saige:mfa:{digest}"
        raw_user = await self._kv.get(ticket_key)
        if raw_user is None:
            raise UnauthorizedError("That sign-in expired. Please enter your password again.")
        attempts = await self._kv.incr(
            f"saige:mfa_attempts:{digest}", ttl_seconds=MFA_TICKET_SECONDS
        )
        if attempts > MFA_MAX_ATTEMPTS:
            await self._kv.pop(ticket_key)
            raise RateLimitedError("Too many incorrect codes. Please sign in again.")
        user = await self._user(uuid.UUID(raw_user))
        if user is None or not await self._accept_second_factor(user, code):
            raise InvalidCodeError("That code isn't valid. Check your authenticator app.")
        if await self._kv.pop(ticket_key) is None:  # concurrent use of one ticket
            raise UnauthorizedError("That sign-in expired. Please enter your password again.")
        await self._db.users.update_one({"_id": user.id}, {"$set": {"last_login_at": now()}})
        return user

    # -- second factor --------------------------------------------------------

    def _require_cipher(self) -> TokenCipher:
        if self._cipher is None:
            raise TwoFactorUnavailableError(
                "Two-step verification needs TOKEN_ENCRYPTION_KEY on the server."
            )
        return self._cipher

    def _secret(self, user: Doc) -> str | None:
        blob = (user.password or {}).get("totp_secret")
        if blob is None:
            return None
        return self._require_cipher().decrypt(bytes(blob), associated_data=_totp_aad(user.id))

    async def _accept_second_factor(self, user: Doc, code: str) -> bool:
        """TOTP code (replay-protected) or a single-use recovery code. Atomic."""
        credential = user.password or {}
        secret = self._secret(user)
        if secret is None or credential.get("totp_enabled_at") is None:
            return False
        step = totp.verify(secret, code, last_used_step=credential.get("totp_last_step"))
        if step >= 0:
            # Only advance if no other request used this or a later step meanwhile.
            result = await self._db.users.update_one(
                {
                    "_id": user.id,
                    "$or": [
                        {"password.totp_last_step": None},
                        {"password.totp_last_step": {"$lt": step}},
                    ],
                },
                {"$set": {"password.totp_last_step": step}},
            )
            return bool(result.modified_count)
        hashed = totp.hash_recovery_code(code)
        result = await self._db.users.update_one(
            {"_id": user.id, "password.recovery_hashes": hashed},
            {"$pull": {"password.recovery_hashes": hashed}},
        )
        return bool(result.modified_count)

    async def verify_password_for(self, user_id: uuid.UUID, password: str) -> Doc:
        """Step-up check for sensitive changes; shares the per-account lockout."""
        user = await self._user(user_id)
        fail_key = await self._check_lockout(user.email if user else str(user_id))
        credential = user.password if user else None
        if not passwords.verify_password(credential["hash"] if credential else None, password):
            await self._kv.incr(fail_key, ttl_seconds=LOCKOUT_SECONDS)
            raise IncorrectPasswordError("Your current password is incorrect.")
        assert user is not None  # noqa: S101
        return user

    async def begin_totp_setup(self, user: Doc) -> tuple[str, str]:
        if (user.password or {}).get("totp_enabled_at") is not None:
            raise ConflictError("Two-step verification is already on.")
        cipher = self._require_cipher()
        secret = totp.new_secret()
        await self._db.users.update_one(
            {"_id": user.id},
            {
                "$set": {
                    "password.totp_secret": cipher.encrypt(
                        secret, associated_data=_totp_aad(user.id)
                    ),
                    "password.totp_key_version": cipher.current_version,
                    "password.totp_last_step": None,
                }
            },
        )
        return secret, totp.provisioning_uri(secret, account=user.email)

    async def enable_totp(self, user_id: uuid.UUID, code: str) -> list[str]:
        user = await self._user(user_id)
        credential = (user.password if user else None) or {}
        if user is None or credential.get("totp_secret") is None:
            raise ConflictError("Start two-step verification setup first.")
        if credential.get("totp_enabled_at") is not None:
            raise ConflictError("Two-step verification is already on.")
        secret = self._secret(user)
        assert secret is not None  # noqa: S101
        step = totp.verify(secret, code, last_used_step=None)
        if step < 0:
            raise InvalidCodeError("That code isn't valid. Check your authenticator app.")
        codes = totp.new_recovery_codes()
        await self._db.users.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "password.totp_last_step": step,
                    "password.totp_enabled_at": now(),
                    "password.recovery_hashes": [totp.hash_recovery_code(c) for c in codes],
                }
            },
        )
        return codes

    async def disable_totp(self, user: Doc, code: str) -> None:
        if (user.password or {}).get("totp_enabled_at") is None:
            raise ConflictError("Two-step verification is already off.")
        if not await self._accept_second_factor(user, code):
            raise InvalidCodeError("That code isn't valid. Check your authenticator app.")
        await self._db.users.update_one(
            {"_id": user.id},
            {
                "$set": {
                    "password.totp_secret": None,
                    "password.totp_key_version": None,
                    "password.totp_enabled_at": None,
                    "password.totp_last_step": None,
                    "password.recovery_hashes": [],
                }
            },
        )

    # -- password changes -----------------------------------------------------

    async def set_password(self, user_id: uuid.UUID, new_password: str) -> None:
        user = await self._user(user_id)
        if user is None:
            return
        if user.password:
            await self._db.users.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "password.hash": passwords.hash_password(new_password),
                        "password.changed_at": now(),
                    }
                },
            )
        else:
            await self._db.users.update_one(
                {"_id": user_id}, {"$set": {"password": new_credential(new_password)}}
            )
