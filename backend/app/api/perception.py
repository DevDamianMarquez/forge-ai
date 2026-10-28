"""The one endpoint for Milestone 3B: build a PhysicalSystem from a PerceptionResult.

Purely deterministic -- no Muse, no Meta, no network. Calls the exact same
`build_physical_system` function the test suite calls; no boundary logic is
duplicated here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.perception import PerceptionResult, PhysicalSystemBuildResult
from app.perception.builder import build_physical_system

router = APIRouter(prefix="/perception", tags=["perception"])


@router.post("/build-physical-system", response_model=PhysicalSystemBuildResult)
def create_physical_system_from_perception(perception: PerceptionResult) -> PhysicalSystemBuildResult:
    """Deterministically build a PhysicalSystem from `perception`, or refuse (422).

    On refusal, the response body's `detail` is the list of structured
    PerceptionIssues explaining exactly what was missing or unconfirmed.
    """
    result = build_physical_system(perception)
    if result.physical_system is None:
        raise HTTPException(
            status_code=422,
            detail=[issue.model_dump(mode="json") for issue in result.issues],
        )
    return result
