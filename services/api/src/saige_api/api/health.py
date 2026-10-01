"""Liveness (/health) and readiness (/ready) probes."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from saige_api import __version__
from saige_api.api.deps import ResourcesDep
from saige_api.health import CheckStatus, run_checks
from saige_api.schemas.system import DependencyStatus, LivenessResponse, ReadinessResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=LivenessResponse, summary="Liveness probe")
async def health() -> LivenessResponse:
    """Returns 200 while the process is able to serve requests. Performs no I/O."""
    return LivenessResponse(service="saige-api", version=__version__)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    responses={503: {"model": ReadinessResponse, "description": "A critical dependency is down"}},
)
async def ready(resources: ResourcesDep, response: Response) -> ReadinessResponse:
    results = await run_checks(
        resources.health_checks, resources.settings.readiness_timeout_seconds
    )
    critical_failed = any(r.critical and r.status is CheckStatus.FAIL for r in results)
    any_failed = any(r.status is CheckStatus.FAIL for r in results)
    if critical_failed:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        overall = "not_ready"
    else:
        overall = "degraded" if any_failed else "ready"
    response.headers["Cache-Control"] = "no-store"
    return ReadinessResponse(
        status=overall,
        version=__version__,
        environment=resources.settings.app_env.value,
        checks=[
            DependencyStatus(
                name=r.name,
                status=r.status.value,
                critical=r.critical,
                latency_ms=r.latency_ms,
                detail=r.detail,
            )
            for r in results
        ],
    )
