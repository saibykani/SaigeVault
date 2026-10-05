"""Find-or-create users from verified identities."""

from __future__ import annotations

import contextlib
from datetime import timedelta
from typing import Any

from pymongo.errors import DuplicateKeyError

from saige_api.auth.google import GoogleIdentity
from saige_api.auth.sessions import RevokeReason, SessionService
from saige_api.core.errors import ForbiddenError
from saige_api.core.logging import get_logger
from saige_api.db import Doc, new_id, now
from saige_api.enums import UserStatus

GOOGLE_PROVIDER = "google"
logger = get_logger("saige_api.auth.users")


def new_user(email: str, display_name: str | None = None) -> dict[str, Any]:
    at = now()
    return {
        "_id": new_id(),
        "email": email.strip(),
        "email_lower": email.strip().lower(),
        "display_name": display_name,
        "avatar_url": None,
        "status": UserStatus.ACTIVE.value,
        "email_verified_at": None,
        "last_login_at": None,
        "password": None,
        "created_at": at,
        "updated_at": at,
        "deleted_at": None,
    }


async def find_user_by_email(db: Any, email: str) -> Doc | None:
    raw = await db.users.find_one({"email_lower": email.strip().lower()})
    return Doc(raw) if raw else None


async def _insert_or_get(db: Any, email: str, display_name: str | None) -> Doc:
    try:
        user = new_user(email, display_name)
        await db.users.insert_one(user)
        return Doc(user)
    except DuplicateKeyError:  # concurrent sign-up with the same email
        found = await find_user_by_email(db, email)
        assert found is not None  # noqa: S101
        return found


def _ensure_usable(user: Doc) -> Doc:
    if user.deleted_at is not None or user.status != UserStatus.ACTIVE.value:
        raise ForbiddenError("This account is disabled")
    return user


async def _evict_unverified_claim(db: Any, user: Doc) -> None:
    """Defeat account pre-hijacking.

    Anyone can sign up with a password using someone else's address. When the
    real owner later proves the address through Google, any password set
    before that proof is removed and existing sessions are ended, so a
    squatter never shares the owner's vault.
    """
    if user.password:
        await db.users.update_one({"_id": user.id}, {"$set": {"password": None}})
        logger.warning("unverified_password_removed", user_id=str(user.id))
    await SessionService(db, timedelta(0)).revoke_all(user.id, RevokeReason.ACCOUNT_SECURED)


async def user_for_google_identity(db: Any, identity: GoogleIdentity) -> Doc:
    at = now()
    account = await db.oauth_accounts.find_one(
        {"provider": GOOGLE_PROVIDER, "subject": identity.subject}
    )
    if account is not None:
        raw = await db.users.find_one({"_id": account["user_id"]})
        if raw is None:
            raise ForbiddenError("This account is unavailable")
        user = Doc(raw)
        await db.oauth_accounts.update_one(
            {"_id": account["_id"]}, {"$set": {"email": identity.email, "last_used_at": at}}
        )
    else:
        # Linking by email is safe only because Google verified the address.
        found = await find_user_by_email(db, identity.email)
        if found is None:
            user = await _insert_or_get(db, identity.email, identity.name)
        else:
            user = found
            if user.email_verified_at is None:
                await _evict_unverified_claim(db, user)
        with contextlib.suppress(DuplicateKeyError):  # concurrent first sign-in
            await db.oauth_accounts.insert_one(
                {
                    "_id": new_id(),
                    "user_id": user.id,
                    "provider": GOOGLE_PROVIDER,
                    "subject": identity.subject,
                    "email": identity.email,
                    "created_at": at,
                    "last_used_at": at,
                }
            )
    _ensure_usable(user)
    updates = {
        "email_verified_at": user.email_verified_at or at,
        "display_name": identity.name or user.display_name,
        "avatar_url": identity.picture or user.avatar_url,
        "last_login_at": at,
        "updated_at": at,
    }
    await db.users.update_one({"_id": user.id}, {"$set": updates})
    user.update(updates)
    return user


async def user_for_dev_login(db: Any, email: str, display_name: str | None) -> Doc:
    user = await find_user_by_email(db, email) or await _insert_or_get(db, email, display_name)
    _ensure_usable(user)
    await db.users.update_one({"_id": user.id}, {"$set": {"last_login_at": now()}})
    return user
