"""The one endpoint for Milestone 1: run a gear-train experiment over HTTP.

Exists only to verify the physics layer end-to-end through the API shape
FORGE will eventually use. It calls the exact same `run_gear_train_experiment`
function the test suite calls -- no calculation logic is duplicated here.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.models.physics import Constraint, ExperimentResult, GearTrain
from app.physics.experiments import run_gear_train_experiment

router = APIRouter(prefix="/experiments", tags=["experiments"])


class GearTrainExperimentRequest(BaseModel):
    """The request body: a gear train plus any constraints to evaluate against it."""

    train: GearTrain
    constraints: list[Constraint] = Field(default_factory=list)


@router.post("/gear-train", response_model=ExperimentResult)
def create_gear_train_experiment(request: GearTrainExperimentRequest) -> ExperimentResult:
    """Run one deterministic gear-train experiment and return its ExperimentResult."""
    return run_gear_train_experiment(request.train, request.constraints)
