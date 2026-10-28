"""FORGE backend entrypoint.

Milestone 1 added the deterministic physics engine and its one endpoint.
Milestone 2A added the Muse Spark <-> FORGE tool-call integration endpoint.
Milestone 3A added the explicit PhysicalSystem topology endpoint. Milestone
3B adds the perception-to-PhysicalSystem boundary endpoint, unchanged
otherwise. No database, authentication, or deployment concerns exist yet.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.experiments import router as experiments_router
from app.api.forge import router as forge_router
from app.api.perception import router as perception_router

app = FastAPI(title="FORGE Physics Engine", version="0.3.0")
app.include_router(experiments_router, prefix="/api/v1")
app.include_router(forge_router, prefix="/api/v1")
app.include_router(perception_router, prefix="/api/v1")
