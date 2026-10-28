"""Deterministic physics endpoints: no Muse, no Meta, no network calls.

Milestone 1 added POST /gear-train. Milestone 3A adds POST /physical-system,
unchanged otherwise. Both call the exact same deterministic functions the
test suite calls -- no calculation logic is duplicated here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.physics import (
    Constraint,
    ExperimentResult,
    GearTrain,
    PhysicalSystem,
    PhysicalSystemExperimentResult,
)
from app.physics.experiments import run_gear_train_experiment
from app.physics.topology import UnsupportedTopologyError, run_physical_system_experiment

router = APIRouter(prefix="/experiments", tags=["experiments"])


class GearTrainExperimentRequest(BaseModel):
    """The request body: a gear train plus any constraints to evaluate against it."""

    train: GearTrain
    constraints: list[Constraint] = Field(default_factory=list)


@router.post("/gear-train", response_model=ExperimentResult)
def create_gear_train_experiment(request: GearTrainExperimentRequest) -> ExperimentResult:
    """Run one deterministic gear-train experiment and return its ExperimentResult."""
    return run_gear_train_experiment(request.train, request.constraints)


@router.post("/physical-system", response_model=PhysicalSystemExperimentResult)
def create_physical_system_experiment(system: PhysicalSystem) -> PhysicalSystemExperimentResult:
    """Compile a PhysicalSystem's topology into a GearTrain and run the deterministic experiment.

    Rejects (422) rather than guesses when the topology is branched, cyclic,
    disconnected, or otherwise ambiguous -- see app.physics.topology.
    """
    try:
        return run_physical_system_experiment(system)
    except UnsupportedTopologyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
