"""MongoDB access.

Every query on user data filters by `user_id`: that is the tenant boundary.
Ids are UUIDs (stored as BSON binary subtype 4), dates are timezone-aware UTC.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.uri_parser import parse_uri

DEFAULT_DB = "saige_vault"


def now() -> datetime:
    return datetime.now(UTC)


def new_id() -> uuid.UUID:
    return uuid.uuid4()


class Doc(dict[str, Any]):
    """A Mongo document with attribute access (`doc.name`, `doc.id` for `_id`).

    Missing keys read as None, so older documents tolerate new optional fields.
    """

    def __getattr__(self, name: str) -> Any:
        if name == "id":
            return self.get("_id")
        return self.get(name)


def doc(raw: dict[str, Any] | None) -> Doc | None:
    return Doc(raw) if raw is not None else None


def create_client(uri: str) -> AsyncMongoClient[dict[str, Any]]:
    return AsyncMongoClient(
        uri,
        uuidRepresentation="standard",
        tz_aware=True,
        tzinfo=UTC,
        serverSelectionTimeoutMS=8000,
        appname="saige-api",
    )


def database_name(uri: str) -> str:
    try:
        return parse_uri(uri).get("database") or DEFAULT_DB
    except Exception:
        return DEFAULT_DB


async def ensure_indexes(db: AsyncDatabase[dict[str, Any]]) -> None:
    await db.users.create_index("email_lower", unique=True)
    await db.oauth_accounts.create_index(
        [("provider", ASCENDING), ("subject", ASCENDING)], unique=True
    )
    await db.sessions.create_index("refresh_token_hash", unique=True)
    await db.sessions.create_index([("user_id", ASCENDING), ("family_id", ASCENDING)])
    # Expired sessions are removed automatically.
    await db.sessions.create_index("expires_at", expireAfterSeconds=0)
    await db.files.create_index(
        [("user_id", ASCENDING), ("folder_id", ASCENDING), ("deleted_at", ASCENDING)]
    )
    await db.files.create_index([("user_id", ASCENDING), ("updated_at", DESCENDING)])
    await db.files.create_index("object_key", unique=True)
    await db.folders.create_index([("user_id", ASCENDING), ("parent_id", ASCENDING)])
    await db.tags.create_index([("user_id", ASCENDING), ("name_lower", ASCENDING)], unique=True)
    await db.collections.create_index([("user_id", ASCENDING), ("name_lower", ASCENDING)])
    await db.audit_logs.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db.security_events.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
