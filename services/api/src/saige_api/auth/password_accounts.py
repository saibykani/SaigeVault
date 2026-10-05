"""Email + password accounts with an optional TOTP second factor."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saige_api.auth import passwords, totp
from saige_api.core.errors import AppError, ConflictError, RateLimitedError, UnauthorizedError
from saige_api.crypto import TokenCipher
from saige_api.kv import KeyValueStore
from saige_api.models import PasswordCredential, User
from saige_api.models.enums import UserStatus

# Per-account brute-force protection, independent of the per-IP limit, so a
# botnet spreading guesses across addresses still gets 5 tries per 15 minutes.
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60
MFA_TICKET_SECONDS = 5 * 60
MFA_MAX_ATTEMPTS = 5

INVALID_CREDENTIALS = "Email or password is incorrect."


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


def _totp_aad(credential_id: uuid.UUID) -> str:
    return f"password_credential:{credential_id}:totp"


@dataclass(frozen=True, slots=True)
class LoginResult:
    user: User
    mfa_ticket: str | None = None


class PasswordAccountService:
    def __init__(self, db: AsyncSession, kv: KeyValueStore, cipher: TokenCipher | None) -> None:
        self._db = db
        self._kv = kv
        self._cipher = cipher

    # -- lookups ------------------------------------------------------------

    async def credential_for(
        self, user_id: uuid.UUID, *, for_update: bool = False
    ) -> PasswordCredential | None:
        query = select(PasswordCredential).where(PasswordCredential.user_id == user_id)
        if for_update:
            query = query.with_for_update()
        return await self._db.scalar(query)

    async def _user_by_email(self, email: str) -> User | None:
        return await self._db.scalar(
            select(User).where(func.lower(User.email) == email.strip().lower())
        )

    # -- registration ---------------------------------------------------------

    async def register(self, email: str, password: str, display_name: str | None) -> User:
        email = email.strip()
        if await self._user_by_email(email) is not None:
            raise ConflictError(
                "An account with this email already exists. Sign in instead, or use "
                "Continue with Google if that's how you joined."
            )
        user = User(email=email, display_name=display_name, status=UserStatus.ACTIVE)
        self._db.add(user)
        await self._db.flush()
        self._db.add(
            PasswordCredential(user_id=user.id, password_hash=passwords.hash_password(password))
        )
        user.last_login_at = datetime.now(UTC)
        await self._db.flush()
        return user

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
        user = await self._user_by_email(email)
        credential = await self.credential_for(user.id) if user is not None else None
        # Always run one Argon2 verification so timing doesn't reveal accounts.
        ok = passwords.verify_password(credential.password_hash if credential else None, password)
        if not ok or user is None or credential is None:
            await self._kv.incr(fail_key, ttl_seconds=LOCKOUT_SECONDS)
            raise InvalidCredentialsError(INVALID_CREDENTIALS)
        if user.deleted_at is not None or user.status is not UserStatus.ACTIVE:
            raise InvalidCredentialsError(INVALID_CREDENTIALS)
        await self._kv.pop(fail_key)
        if passwords.needs_rehash(credential.password_hash):
            credential.password_hash = passwords.hash_password(password)
        if credential.totp_enabled_at is not None:
            return LoginResult(user=user, mfa_ticket=await self._issue_mfa_ticket(user.id))
        user.last_login_at = datetime.now(UTC)
        await self._db.flush()
        return LoginResult(user=user)

    async def _issue_mfa_ticket(self, user_id: uuid.UUID) -> str:
        ticket = secrets.token_urlsafe(32)
        await self._kv.set(
            f"saige:mfa:{hashlib.sha256(ticket.encode()).hexdigest()}",
            str(user_id),
            ttl_seconds=MFA_TICKET_SECONDS,
        )
        return ticket

    async def complete_mfa(self, ticket: str, code: str) -> User:
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
        user_id = uuid.UUID(raw_user)
        credential = await self.credential_for(user_id, for_update=True)
        user = await self._db.get(User, user_id)
        if credential is None or user is None or not self._accept_second_factor(credential, code):
            raise InvalidCodeError("That code isn't valid. Check your authenticator app.")
        if await self._kv.pop(ticket_key) is None:  # concurrent use of one ticket
            raise UnauthorizedError("That sign-in expired. Please enter your password again.")
        user.last_login_at = datetime.now(UTC)
        await self._db.flush()
        return user

    # -- second factor --------------------------------------------------------

    def _require_cipher(self) -> TokenCipher:
        if self._cipher is None:
            raise TwoFactorUnavailableError(
                "Two-step verification needs TOKEN_ENCRYPTION_KEY on the server."
            )
        return self._cipher

    def _secret(self, credential: PasswordCredential) -> str | None:
        if credential.encrypted_totp_secret is None:
            return None
        return self._require_cipher().decrypt(
            credential.encrypted_totp_secret, associated_data=_totp_aad(credential.id)
        )

    def _accept_second_factor(self, credential: PasswordCredential, code: str) -> bool:
        """TOTP code (replay-protected) or a single-use recovery code."""
        secret = self._secret(credential)
        if secret is None or credential.totp_enabled_at is None:
            return False
        step = totp.verify(secret, code, last_used_step=credential.totp_last_used_step)
        if step >= 0:
            credential.totp_last_used_step = step
            return True
        hashed = totp.hash_recovery_code(code)
        if hashed in credential.recovery_code_hashes:
            credential.recovery_code_hashes = [
                h for h in credential.recovery_code_hashes if h != hashed
            ]
            return True
        return False

    async def verify_password_for(self, user_id: uuid.UUID, password: str) -> PasswordCredential:
        """Step-up check for sensitive changes; shares the per-account lockout."""
        user = await self._db.get(User, user_id)
        email = user.email if user else str(user_id)
        fail_key = await self._check_lockout(email)
        credential = await self.credential_for(user_id, for_update=True)
        if not passwords.verify_password(
            credential.password_hash if credential else None, password
        ):
            await self._kv.incr(fail_key, ttl_seconds=LOCKOUT_SECONDS)
            raise IncorrectPasswordError("Your current password is incorrect.")
        assert credential is not None  # noqa: S101 - verify_password(None, ...) is False
        return credential

    async def begin_totp_setup(
        self, credential: PasswordCredential, account: str
    ) -> tuple[str, str]:
        if credential.totp_enabled_at is not None:
            raise ConflictError("Two-step verification is already on.")
        cipher = self._require_cipher()
        secret = totp.new_secret()
        credential.encrypted_totp_secret = cipher.encrypt(
            secret, associated_data=_totp_aad(credential.id)
        )
        credential.totp_key_version = cipher.current_version
        credential.totp_last_used_step = None
        await self._db.flush()
        return secret, totp.provisioning_uri(secret, account=account)

    async def enable_totp(self, user_id: uuid.UUID, code: str) -> list[str]:
        credential = await self.credential_for(user_id, for_update=True)
        if credential is None or credential.encrypted_totp_secret is None:
            raise ConflictError("Start two-step verification setup first.")
        if credential.totp_enabled_at is not None:
            raise ConflictError("Two-step verification is already on.")
        secret = self._secret(credential)
        assert secret is not None  # noqa: S101
        step = totp.verify(secret, code, last_used_step=None)
        if step < 0:
            raise InvalidCodeError("That code isn't valid. Check your authenticator app.")
        codes = totp.new_recovery_codes()
        credential.totp_last_used_step = step
        credential.totp_enabled_at = datetime.now(UTC)
        credential.recovery_code_hashes = [totp.hash_recovery_code(c) for c in codes]
        await self._db.flush()
        return codes

    async def disable_totp(self, credential: PasswordCredential, code: str) -> None:
        if credential.totp_enabled_at is None:
            raise ConflictError("Two-step verification is already off.")
        if not self._accept_second_factor(credential, code):
            raise InvalidCodeError("That code isn't valid. Check your authenticator app.")
        credential.encrypted_totp_secret = None
        credential.totp_key_version = None
        credential.totp_enabled_at = None
        credential.totp_last_used_step = None
        credential.recovery_code_hashes = []
        await self._db.flush()

    # -- password changes -----------------------------------------------------

    async def set_password(self, user_id: uuid.UUID, new_password: str) -> None:
        credential = await self.credential_for(user_id, for_update=True)
        if credential is None:
            self._db.add(
                PasswordCredential(
                    user_id=user_id, password_hash=passwords.hash_password(new_password)
                )
            )
        else:
            credential.password_hash = passwords.hash_password(new_password)
            credential.password_changed_at = datetime.now(UTC)
        await self._db.flush()
