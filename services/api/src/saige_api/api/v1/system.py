"""/api/v1/system — non-sensitive capability discovery for clients."""

from __future__ import annotations

from fastapi import APIRouter

from saige_api import __version__
from saige_api.api.deps import ResourcesDep
from saige_api.schemas.system import SystemInfoResponse

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/info", response_model=SystemInfoResponse, summary="Server capabilities")
async def system_info(resources: ResourcesDep) -> SystemInfoResponse:
    settings = resources.settings
    return SystemInfoResponse(
        version=__version__,
        environment=settings.app_env.value,
        ai_processing_policy=settings.ai_processing_policy.value,
        google_oauth_configured=settings.google_oauth_configured,
        dev_login_enabled=settings.dev_login_enabled and not settings.is_production,
        google_drive_available=settings.google_drive_available,
        password_login_enabled=settings.password_login_enabled,
    )
