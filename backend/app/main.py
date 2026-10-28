"""FORGE backend entrypoint (Milestone 1: physics engine only).

No Meta AI integration, no other workflow-stage routers, no database, and no
authentication exist yet -- this only wires up the one physics-verification
endpoint built for this milestone.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.experiments import router as experiments_router

app = FastAPI(title="FORGE Physics Engine", version="0.1.0")
app.include_router(experiments_router, prefix="/api/v1")
