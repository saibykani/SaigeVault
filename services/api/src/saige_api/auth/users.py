"""Find-or-create users from verified identities."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saige_api.auth.google import GoogleIdentity
from saige_api.core.errors import ForbiddenError
from saige_api.models import OAuthAccount, User
from saige_api.models.enums import UserStatus

GOOGLE_PROVIDER = "google"


async def _ensure_usable(user: User) -> User:
    if user.deleted_at is not None or user.status is not UserStatus.ACTIVE:
        raise ForbiddenError("This account is disabled")
    return user


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
