"""Session lifecycle: creation, refresh-token rotation, reuse detection, revocation.

A *session* is a family of `sessions` documents sharing `family_id`. Each
refresh rotates the token: the presented document is atomically marked
`rotated` and a new one is added. Presenting a token that was already rotated
means it leaked (or was replayed) — the whole family is revoked. A short grace
window tolerates two tabs refreshing at once.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from pymongo import ReturnDocument

from saige_api.auth.tokens import hash_token, new_refresh_token
from saige_api.db import Doc, now
from saige_api.enums import ClientPlatform

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
    def __init__(self, db: Any, refresh_ttl: timedelta) -> None:
        self._sessions = db.sessions
        self._ttl = refresh_ttl

    async def create(self, user_id: uuid.UUID, client: ClientInfo) -> IssuedSession:
        return await self._add_generation(user_id, uuid.uuid4(), client, rotated_from=None)

    async def rotate(self, refresh_token: str, client: ClientInfo) -> RefreshResult:
        at = now()
        token_hash = hash_token(refresh_token)
        # Atomic claim: only one request can rotate a given token.
        claimed = await self._sessions.find_one_and_update(
            {"refresh_token_hash": token_hash, "revoked_at": None, "expires_at": {"$gt": at}},
            {"$set": {"revoked_at": at, "revoked_reason": RevokeReason.ROTATED.value}},
            return_document=ReturnDocument.BEFORE,
        )
        if claimed is not None:
            issued = await self._add_generation(
                claimed["user_id"], claimed["family_id"], client, rotated_from=claimed["_id"]
            )
            return RefreshResult(
                RefreshOutcome.ROTATED,
                issued=issued,
                user_id=claimed["user_id"],
                session_id=claimed["family_id"],
            )
        row = await self._sessions.find_one({"refresh_token_hash": token_hash})
        if row is None:
            return RefreshResult(RefreshOutcome.INVALID)
        user_id, family_id = row["user_id"], row["family_id"]
        if row.get("revoked_reason") == RevokeReason.ROTATED.value and row.get("revoked_at"):
            if at - row["revoked_at"] <= ROTATION_GRACE:
                return RefreshResult(RefreshOutcome.RACE, user_id=user_id, session_id=family_id)
            await self.revoke_family(user_id, family_id, RevokeReason.REUSE_DETECTED)
            return RefreshResult(
                RefreshOutcome.REUSE_DETECTED, user_id=user_id, session_id=family_id
            )
        return RefreshResult(RefreshOutcome.INVALID, user_id=user_id, session_id=family_id)

    async def find_family_by_refresh_token(
        self, refresh_token: str
    ) -> tuple[uuid.UUID, uuid.UUID] | None:
        row = await self._sessions.find_one({"refresh_token_hash": hash_token(refresh_token)})
        return (row["user_id"], row["family_id"]) if row else None

    async def is_active(self, user_id: uuid.UUID, family_id: uuid.UUID) -> bool:
        found = await self._sessions.find_one(
            {
                "user_id": user_id,
                "family_id": family_id,
                "revoked_at": None,
                "expires_at": {"$gt": now()},
            },
            projection={"_id": 1},
        )
        return found is not None

    async def revoke_family(
        self, user_id: uuid.UUID, family_id: uuid.UUID, reason: RevokeReason
    ) -> int:
        result = await self._sessions.update_many(
            {"user_id": user_id, "family_id": family_id, "revoked_at": None},
            {"$set": {"revoked_at": now(), "revoked_reason": reason.value}},
        )
        return int(result.modified_count)

    async def revoke_all(
        self, user_id: uuid.UUID, reason: RevokeReason, *, except_family: uuid.UUID | None = None
    ) -> int:
        query: dict[str, Any] = {"user_id": user_id, "revoked_at": None}
        if except_family is not None:
            query["family_id"] = {"$ne": except_family}
        result = await self._sessions.update_many(
            query, {"$set": {"revoked_at": now(), "revoked_reason": reason.value}}
        )
        return int(result.modified_count)

    async def list_active(self, user_id: uuid.UUID) -> list[tuple[Doc, datetime]]:
        """Active sessions with the time each session family started."""
        started: dict[uuid.UUID, datetime] = {}
        async for row in self._sessions.find(
            {"user_id": user_id}, projection={"family_id": 1, "created_at": 1}
        ):
            fam, created = row["family_id"], row["created_at"]
            if fam not in started or created < started[fam]:
                started[fam] = created
        active = [
            Doc(r)
            async for r in self._sessions.find(
                {"user_id": user_id, "revoked_at": None, "expires_at": {"$gt": now()}}
            ).sort("last_seen_at", -1)
        ]
        return [(r, started.get(r.family_id, r.created_at)) for r in active]

    async def _add_generation(
        self,
        user_id: uuid.UUID,
        family_id: uuid.UUID,
        client: ClientInfo,
        *,
        rotated_from: uuid.UUID | None,
    ) -> IssuedSession:
        token = new_refresh_token()
        at = now()
        expires_at = at + self._ttl
        await self._sessions.insert_one(
            {
                "_id": uuid.uuid4(),
                "user_id": user_id,
                "family_id": family_id,
                "refresh_token_hash": hash_token(token),
                "platform": client.platform.value,
                "user_agent": (client.user_agent or "")[:512] or None,
                "ip_address": client.ip_address,
                "created_at": at,
                "last_seen_at": at,
                "expires_at": expires_at,
                "revoked_at": None,
                "revoked_reason": None,
                "rotated_from": rotated_from,
            }
        )
        return IssuedSession(
            session_id=family_id, user_id=user_id, refresh_token=token, expires_at=expires_at
        )
