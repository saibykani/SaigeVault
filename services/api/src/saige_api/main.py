"""Application factory and ASGI entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from saige_api import __version__
from saige_api.api import health
from saige_api.api.v1.router import api_router
from saige_api.core.config import Settings, get_settings
from saige_api.core.errors import register_exception_handlers
from saige_api.core.logging import configure_logging, get_logger
from saige_api.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from saige_api.resources import Resources
from saige_api.schemas.system import ErrorResponse

logger = get_logger("saige_api")

ResourceFactory = Callable[[Settings], Resources]


def create_app(
    settings: Settings | None = None,
    *,
    resource_factory: ResourceFactory = Resources.create,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json_output=settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resources = resource_factory(settings)
        app.state.resources = resources
        logger.info("startup", version=__version__, environment=settings.app_env.value)
        try:
            yield
        finally:
            await resources.aclose()
            logger.info("shutdown")

    app = FastAPI(
        title="Saige Vault API",
        version=__version__,
        description="Private AI-powered personal document vault.",
        lifespan=lifespan,
        # Interactive docs are a development aid; the OpenAPI spec is
        # published in docs/api/openapi.json for production consumers.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
        responses={
            422: {"model": ErrorResponse, "description": "Validation error"},
            500: {"model": ErrorResponse, "description": "Internal error"},
        },
    )

    # Order: last added runs first. Request context wraps everything so every
    # response (including errors) carries a request ID and security headers.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-CSRF-Token"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )
    app.add_middleware(SecurityHeadersMiddleware, enable_hsts=settings.is_production)
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(api_router)
    return app


def run() -> None:
    import uvicorn  # noqa: PLC0415

    uvicorn.run(
        "saige_api.main:create_app",
        factory=True,
        host="0.0.0.0",  # noqa: S104 - bound inside the container network
        port=8000,
        proxy_headers=True,
        server_header=False,
    )
