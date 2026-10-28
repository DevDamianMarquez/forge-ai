"""The one demo/development endpoint for Milestone 4A: run the deterministic
perception-to-physics pipeline against a known fixture.

EXPLICITLY A DEVELOPMENT/DEMO ENDPOINT. The perception here is a
hand-authored deterministic fixture (see
``app.perception.providers.fixture``), never a real vision model -- nothing
about this endpoint implies image analysis occurred. No Muse, no Meta, no
network.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.perception import PerceptionRequest
from app.perception.providers.fixture import FixturePerceptionProvider, UnknownFixtureError
from app.services.physical_pipeline import PhysicalPipelineResult, run_physical_pipeline

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

_provider = FixturePerceptionProvider()


@router.post("/run-fixture", response_model=PhysicalPipelineResult)
def run_fixture_pipeline(request: PerceptionRequest) -> PhysicalPipelineResult:
    """Run the deterministic pipeline against a known fixture_id, or refuse (404).

    Calls the exact same ``run_physical_pipeline`` function the test suite
    calls -- no pipeline logic is duplicated here.
    """
    try:
        return run_physical_pipeline(_provider, request)
    except UnknownFixtureError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
