"""Single-use OAuth `state` storage in Redis (10-minute TTL)."""

from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass

from saige_api.kv import KeyValueStore

STATE_TTL_SECONDS = 600
_PREFIX = "saige:oauth_state:"


LOGIN = "login"
DRIVE_CONNECT = "drive_connect"


@dataclass(frozen=True, slots=True)
class PendingLogin:
    code_verifier: str
    nonce: str
    next_path: str
    # "login" or "drive_connect". Drive consent is bound to the user who started it.
    purpose: str = LOGIN
    user_id: str | None = None


class OAuthStateStore:
    def __init__(self, store: KeyValueStore) -> None:
        self._store = store

    async def create(self, pending: PendingLogin) -> str:
        state = secrets.token_urlsafe(32)
        await self._store.set(
            _PREFIX + state, json.dumps(asdict(pending)), ttl_seconds=STATE_TTL_SECONDS
        )
        return state

    async def consume(self, state: str) -> PendingLogin | None:
        """Atomically fetch and delete, so a state can never be replayed."""
        if not state or len(state) > 128:
            return None
        raw = await self._store.pop(_PREFIX + state)
        if raw is None:
            return None
        data = json.loads(raw)
        return PendingLogin(**data)


def safe_next_path(candidate: str | None) -> str:
    """Only same-site relative paths are allowed (prevents open redirects)."""
    if not candidate or not candidate.startswith("/") or candidate.startswith("//"):
        return "/"
    if "\\" in candidate or any(ord(ch) < 32 for ch in candidate) or len(candidate) > 512:
        return "/"
    return candidate
