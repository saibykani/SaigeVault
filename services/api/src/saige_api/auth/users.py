"""Find-or-create users from verified identities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saige_api.auth.google import GoogleIdentity
from saige_api.auth.sessions import RevokeReason, SessionService
from saige_api.core.errors import ForbiddenError
from saige_api.core.logging import get_logger
from saige_api.models import OAuthAccount, PasswordCredential, User
from saige_api.models.enums import UserStatus

GOOGLE_PROVIDER = "google"
logger = get_logger("saige_api.auth.users")


async def _ensure_usable(user: User) -> User:
    if user.deleted_at is not None or user.status is not UserStatus.ACTIVE:
        raise ForbiddenError("This account is disabled")
    return user


async def _evict_unverified_claim(db: AsyncSession, user: User) -> None:
    """Defeat account pre-hijacking.

    Anyone can sign up with a password using someone else's address. When the
    real owner later proves the address through Google, any password set
    before that proof is removed and existing sessions are ended, so a
    squatter never shares the owner's vault.
    """
    removed = await db.execute(
        delete(PasswordCredential).where(PasswordCredential.user_id == user.id)
    )
    await SessionService(db, timedelta(0)).revoke_all(user.id, RevokeReason.ACCOUNT_SECURED)
    if getattr(removed, "rowcount", 0):
        logger.warning("unverified_password_removed", user_id=str(user.id))


async def user_for_google_identity(db: AsyncSession, identity: GoogleIdentity) -> User:
    now = datetime.now(UTC)
    account = await db.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == GOOGLE_PROVIDER,
            OAuthAccount.provider_subject == identity.subject,
        )
    )
    if account is not None:
        user = await db.get(User, account.user_id)
        if user is None:  # pragma: no cover - FK guarantees existence
            raise ForbiddenError("This account is unavailable")
        account.email = identity.email
        account.last_used_at = now
    else:
        # Linking by email is safe only because Google verified the address.
        user = await db.scalar(select(User).where(func.lower(User.email) == identity.email.lower()))
        if user is None:
            user = User(email=identity.email, status=UserStatus.ACTIVE)
            db.add(user)
            await db.flush()
        elif user.email_verified_at is None:
            await _evict_unverified_claim(db, user)
        db.add(
            OAuthAccount(
                user_id=user.id,
                provider=GOOGLE_PROVIDER,
                provider_subject=identity.subject,
                email=identity.email,
                last_used_at=now,
            )
        )
    await _ensure_usable(user)
    user.email_verified_at = user.email_verified_at or now
    user.display_name = identity.name or user.display_name
    user.avatar_url = identity.picture or user.avatar_url
    user.last_login_at = now
    await db.flush()
    return user


async def user_for_dev_login(db: AsyncSession, email: str, display_name: str | None) -> User:
    user = await db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None:
        user = User(email=email, display_name=display_name, status=UserStatus.ACTIVE)
        db.add(user)
        await db.flush()
    await _ensure_usable(user)
    user.last_login_at = datetime.now(UTC)
    await db.flush()
    return user
