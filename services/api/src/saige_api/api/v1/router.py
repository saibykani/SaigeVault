"""Aggregates all /api/v1 routers. Feature routers are added phase by phase."""

from __future__ import annotations

from fastapi import APIRouter

from saige_api.api.v1 import auth, system

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(system.router)
api_router.include_router(auth.router)
