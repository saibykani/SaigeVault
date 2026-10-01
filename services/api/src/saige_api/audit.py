"""Audit trail and security events.

`details` must never contain secrets, tokens or document content — only
identifiers and short machine-readable reasons.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from saige_api.models import AuditLog, SecurityEvent
from saige_api.models.enums import ActorType, AuditAction, SecuritySeverity


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def user_agent(request: Request) -> str | None:
    value = request.headers.get("user-agent")
    return value[:512] if value else None


def _request_id(request: Request) -> str | None:
    value = request.scope.get("state", {}).get("request_id")
    return value if isinstance(value, str) else None


def record_audit(
    db: AsyncSession,
    request: Request,
    action: AuditAction,
    *,
    user_id: uuid.UUID | None,
    actor: ActorType = ActorType.USER,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    outcome: str = "success",
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            actor_type=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            request_id=_request_id(request),
            ip_address=client_ip(request),
            user_agent=user_agent(request),
            details=details or {},
        )
    )


def record_security_event(
    db: AsyncSession,
    request: Request,
    event_type: str,
    severity: SecuritySeverity,
    description: str,
    *,
    user_id: uuid.UUID | None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        SecurityEvent(
            user_id=user_id,
            event_type=event_type,
            severity=severity,
            description=description,
            request_id=_request_id(request),
            ip_address=client_ip(request),
            details=details or {},
        )
    )
    record_audit(
        db,
        request,
        AuditAction.SECURITY_EVENT,
        user_id=user_id,
        actor=ActorType.SYSTEM,
        outcome="detected",
        details={"event_type": event_type, "severity": severity.value},
    )
