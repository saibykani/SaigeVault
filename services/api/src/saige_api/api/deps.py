"""FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Request
from pymongo.asynchronous.database import AsyncDatabase

from saige_api.resources import Resources


def get_resources(request: Request) -> Resources:
    resources: Resources = request.app.state.resources
    return resources


ResourcesDep = Annotated[Resources, Depends(get_resources)]


def get_db(resources: ResourcesDep) -> AsyncDatabase[dict[str, Any]]:
    return resources.db


Database = AsyncDatabase[dict[str, Any]]
DbDep = Annotated[Database, Depends(get_db)]
