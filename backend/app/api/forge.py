"""The Milestone 2A integration endpoint: Muse Spark <-> FORGE's physics tool.

Calls the exact same ``run_forge_analysis`` orchestration loop the test
suite exercises -- no duplicated logic. The Muse client is a FastAPI
dependency so tests can override it with a fake and never call the real
Meta Model API.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.models.physics import ExperimentResult, GearTrain
from app.services.autonomous_redesign import (
    AutonomousRedesignResult,
    UnsupportedRedesignTopologyError,
    run_autonomous_redesign,
)
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


class AutonomousRedesignRequest(BaseModel):
    """Milestone 7B.1's request body: trusted starting physical context plus
    the objective Muse must satisfy by choosing only input/output teeth.

    ``starting_train`` reuses the existing Milestone 1 ``GearTrain`` model
    rather than inventing another representation -- it must describe
    exactly one transmission stage (a single external two-gear mesh); its
    ``input_rpm`` becomes the fixed input RPM every candidate is evaluated
    against.
    """

    starting_train: GearTrain
    objective_max_output_rpm: float = Field(..., gt=0)


@router.post("/autonomous-redesign", response_model=AutonomousRedesignResult)
def autonomous_redesign(
    request: AutonomousRedesignRequest,
    client: MuseSparkClient = Depends(get_muse_client),
) -> AutonomousRedesignResult:
    """Run the bounded Muse <-> FORGE autonomous redesign loop.

    Calls the exact same ``run_autonomous_redesign`` function the test
    suite calls -- no orchestration, physics, or constraint logic is
    duplicated here. 7B.1 operates on trusted physical-system data only
    (no image/SAM call); 7A already establishes the physical system this
    endpoint starts from.
    """
    try:
        return run_autonomous_redesign(
            request.starting_train, request.objective_max_output_rpm, client
        )
    except UnsupportedRedesignTopologyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
