"""FORGE backend entrypoint.

Milestone 1 added the deterministic physics engine and its one endpoint.
Milestone 2A added the Muse Spark <-> FORGE tool-call integration endpoint.
Milestone 3A added the explicit PhysicalSystem topology endpoint. Milestone
3B added the perception-to-PhysicalSystem boundary endpoint. Milestone 4A
added the deterministic fixture-perception pipeline demo endpoint.
Milestone 5A adds CORS so the Next.js demo frontend can call this API from
a browser, unchanged otherwise. Milestone 7A.1 adds the real-image
engineering flow (image upload -> SAM -> evidence boundary -> explicit user
confirmation -> deterministic physics). No database, authentication, or
deployment concerns exist yet.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.experiments import router as experiments_router
from app.api.forge import router as forge_router
from app.api.image_analysis import router as image_analysis_router
from app.api.perception import router as perception_router
from app.api.pipeline import router as pipeline_router

app = FastAPI(title="FORGE Physics Engine", version="0.6.0")

# CORS: the demo frontend runs on a different origin (the Next.js dev
# server) and calls this API directly from the browser. Origins are
# configurable via FORGE_CORS_ORIGINS (comma-separated) so this never
# silently allows an unintended origin; it deliberately does not default to
# "*". See .env.example.
_default_cors_origins = "http://localhost:3000,http://127.0.0.1:3000"
_cors_origins = [
    origin.strip()
    for origin in os.environ.get("FORGE_CORS_ORIGINS", _default_cors_origins).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(experiments_router, prefix="/api/v1")
app.include_router(forge_router, prefix="/api/v1")
app.include_router(image_analysis_router, prefix="/api/v1")
app.include_router(perception_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")
