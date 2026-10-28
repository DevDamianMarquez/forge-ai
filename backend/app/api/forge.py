"""The Milestone 2A integration endpoint: Muse Spark <-> FORGE's physics tool.

Calls the exact same ``run_forge_analysis`` orchestration loop the test
suite exercises -- no duplicated logic. The Muse client is a FastAPI
dependency so tests can override it with a fake and never call the real
Meta Model API.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.models.physics import ExperimentResult
from app.services.meta_model import MetaModelClient, MuseSparkClient
from app.services.orchestrator import run_forge_analysis

router = APIRouter(prefix="/forge", tags=["forge"])


class ForgeAnalyzeRequest(BaseModel):
    """The request body: a plain-language objective plus the system data it concerns."""

    objective: str = Field(..., min_length=1)
    system_data: dict[str, Any] = Field(default_factory=dict)


class ForgeAnalyzeResponse(BaseModel):
    """Muse's answer, kept separate from the real ExperimentResult evidence."""

    answer: str | None
    experiments: list[ExperimentResult]
    tool_rounds: int
    status: str


def get_muse_client() -> MuseSparkClient:
    """The real Meta Model API client, constructed lazily per-request.

    Overridden in tests with a fake ``MuseSparkClient`` via
    ``app.dependency_overrides``, so pytest never calls the real API and
    never needs ``MODEL_API_KEY`` to be set.
    """
    return MetaModelClient()


@router.post("/analyze", response_model=ForgeAnalyzeResponse)
def analyze(
    request: ForgeAnalyzeRequest,
    client: MuseSparkClient = Depends(get_muse_client),
) -> ForgeAnalyzeResponse:
    """Run one bounded Muse <-> FORGE tool-call loop for the given objective."""
    result = run_forge_analysis(request.objective, request.system_data, client)
    return ForgeAnalyzeResponse(
        answer=result.answer,
        experiments=result.experiments,
        tool_rounds=result.tool_rounds,
        status=result.status,
    )
