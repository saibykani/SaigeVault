"""Session lifecycle: creation, refresh-token rotation, reuse detection, revocation.

A *session* is a family of `user_sessions` rows sharing `family_id`. Each
refresh rotates the token: the presented row is marked `rotated` and a new
row is added. Presenting a token that was already rotated means it leaked
(or was replayed) — the entire family is revoked and a security event is
recorded. A short grace window tolerates two tabs refreshing at once.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from saige_api.auth.tokens import hash_token, new_refresh_token
from saige_api.models import UserSession
from saige_api.models.enums import ClientPlatform

ROTATION_GRACE = timedelta(seconds=20)


class RevokeReason(StrEnum):
    ROTATED = "rotated"
    LOGOUT = "logout"
    USER_REVOKED = "user_revoked"
    REUSE_DETECTED = "reuse_detected"
    PASSWORD_CHANGED = "password_changed"  # noqa: S105 - a reason label, not a secret
    ACCOUNT_SECURED = "account_secured"


class RefreshOutcome(StrEnum):
    ROTATED = "rotated"
    INVALID = "invalid"
    RACE = "race"  # concurrent refresh inside the grace window
    REUSE_DETECTED = "reuse_detected"


@dataclass(frozen=True, slots=True)
class IssuedSession:
    session_id: uuid.UUID  # family id
    user_id: uuid.UUID
    refresh_token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class RefreshResult:
    outcome: RefreshOutcome
    issued: IssuedSession | None = None
    user_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ClientInfo:
    platform: ClientPlatform
    user_agent: str | None
    ip_address: str | None


class SessionService:
    def __init__(self, db: AsyncSession, refresh_ttl: timedelta) -> None:
        self._db = db
        self._ttl = refresh_ttl

    async def create(self, user_id: uuid.UUID, client: ClientInfo) -> IssuedSession:
        family_id = uuid.uuid4()
        return await self._add_generation(user_id, family_id, client, rotated_from=None)

    async def rotate(self, refresh_token: str, client: ClientInfo) -> RefreshResult:
        now = datetime.now(UTC)
        row = await self._db.scalar(
            select(UserSession)
            .where(UserSession.refresh_token_hash == hash_token(refresh_token))
            .with_for_update()
        )
        if row is None:
            return RefreshResult(RefreshOutcome.INVALID)
        user_id, family_id = row.user_id, row.family_id
        if row.revoked_at is not None:
            if row.revoked_reason == RevokeReason.ROTATED:
                if now - row.revoked_at <= ROTATION_GRACE:
                    return RefreshResult(RefreshOutcome.RACE, user_id=user_id, session_id=family_id)
                await self.revoke_family(row.user_id, row.family_id, RevokeReason.REUSE_DETECTED)
                return RefreshResult(
                    RefreshOutcome.REUSE_DETECTED, user_id=user_id, session_id=family_id
                )
            return RefreshResult(RefreshOutcome.INVALID, user_id=user_id, session_id=family_id)
        if row.expires_at <= now:
            return RefreshResult(RefreshOutcome.INVALID, user_id=user_id, session_id=family_id)

        row.revoked_at = now
        row.revoked_reason = RevokeReason.ROTATED
        issued = await self._add_generation(row.user_id, row.family_id, client, rotated_from=row)
        return RefreshResult(
            RefreshOutcome.ROTATED, issued=issued, user_id=user_id, session_id=family_id
        )

    async def find_family_by_refresh_token(
        self, refresh_token: str
    ) -> tuple[uuid.UUID, uuid.UUID] | None:
        row = await self._db.execute(
            select(UserSession.user_id, UserSession.family_id).where(
                UserSession.refresh_token_hash == hash_token(refresh_token)
            )
        )
        found = row.first()
        return (found.user_id, found.family_id) if found else None

    async def is_active(self, user_id: uuid.UUID, family_id: uuid.UUID) -> bool:
        found = await self._db.scalar(
            select(UserSession.id)
            .where(
                UserSession.user_id == user_id,
                UserSession.family_id == family_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > func.now(),
            )
            .limit(1)
        )
        return found is not None

    async def revoke_family(
        self, user_id: uuid.UUID, family_id: uuid.UUID, reason: RevokeReason
    ) -> int:
        result = await self._db.execute(
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.family_id == family_id,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=func.now(), revoked_reason=reason.value)
        )
        return int(getattr(result, "rowcount", 0) or 0)

    async def revoke_all(
        self, user_id: uuid.UUID, reason: RevokeReason, *, except_family: uuid.UUID | None = None
    ) -> int:
        conditions = [UserSession.user_id == user_id, UserSession.revoked_at.is_(None)]
        if except_family is not None:
            conditions.append(UserSession.family_id != except_family)
        result = await self._db.execute(
            update(UserSession)
            .where(*conditions)
            .values(revoked_at=func.now(), revoked_reason=reason.value)
        )
        return int(getattr(result, "rowcount", 0) or 0)

    async def list_active(self, user_id: uuid.UUID) -> list[tuple[UserSession, datetime]]:
        """Active sessions with the time each session family started."""
        started = (
            select(UserSession.family_id, func.min(UserSession.created_at).label("started_at"))
            .where(UserSession.user_id == user_id)
            .group_by(UserSession.family_id)
            .subquery()
        )
        rows = await self._db.execute(
            select(UserSession, started.c.started_at)
            .join(started, started.c.family_id == UserSession.family_id)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > func.now(),
            )
            .order_by(UserSession.last_seen_at.desc().nulls_last())
        )
        return [(row[0], row[1]) for row in rows.all()]

    async def _add_generation(
        self,
        user_id: uuid.UUID,
        family_id: uuid.UUID,
        client: ClientInfo,
        *,
        rotated_from: UserSession | None,
    ) -> IssuedSession:
        token = new_refresh_token()
        now = datetime.now(UTC)
        expires_at = now + self._ttl
        self._db.add(
            UserSession(
                user_id=user_id,
                family_id=family_id,
                refresh_token_hash=hash_token(token),
                platform=client.platform,
                user_agent=(client.user_agent or "")[:512] or None,
                ip_address=client.ip_address,
                last_seen_at=now,
                expires_at=expires_at,
                rotated_from_id=rotated_from.id if rotated_from else None,
            )
        )
        await self._db.flush()
        return IssuedSession(
            session_id=family_id, user_id=user_id, refresh_token=token, expires_at=expires_at
        )
