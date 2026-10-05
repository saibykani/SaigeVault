"""Response models for system endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: object | None = None


class ErrorResponse(BaseModel):
    """Envelope returned for every non-2xx response."""

    error: ErrorBody


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str


class DependencyStatus(BaseModel):
    name: str
    status: Literal["ok", "fail"]
    critical: bool
    latency_ms: float
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ready", "degraded", "not_ready"] = Field(
        description=(
            "ready: all checks pass. degraded: a non-critical dependency (e.g. Qdrant, "
            "worker) is down; core features work. not_ready: a critical dependency is down."
        )
    )
    version: str
    environment: str
    checks: list[DependencyStatus]


class SystemInfoResponse(BaseModel):
    """Non-sensitive capabilities the clients use to adapt their UI."""

    version: str
    environment: str
    api_version: Literal["v1"] = "v1"
    ai_processing_policy: Literal["disabled", "local_only", "third_party_allowed"]
    google_oauth_configured: bool
    dev_login_enabled: bool = False
    storage_available: bool = Field(
        default=False, description="Uploads are possible (Cloudflare R2 configured)"
    )
    password_login_enabled: bool = True
