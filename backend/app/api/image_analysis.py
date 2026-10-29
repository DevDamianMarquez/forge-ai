"""Milestone 7A.1: the real-image engineering flow's two endpoints.

  A. POST /analyze  -- image upload + prompt -> SAM -> PerceptionResult +
     missing-information issues (never a PhysicalSystem; nothing is
     auto-confirmed).
  B. POST /confirm  -- a round-tripped perception state + explicit USER
     confirmation -> evidence boundary -> deterministic physics, or a
     structured refusal.

No database, no session/persistence layer: /analyze returns the full
perception state, and the frontend simply resends it as part of /confirm's
request body. No Muse, no real Meta call happens in this module's own
code -- the only place a real network call could occur is inside
``app.sam.client.SAMClient``, and tests always inject a fake provider via
dependency override instead.

Uploaded image bytes are read into memory and handed straight to the
provider; they are never written to disk and never logged.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.models.perception import ImagePerceptionRequest, PerceptionResult
from app.perception.providers.sam import SAMPerceptionProvider
from app.physics.topology import UnsupportedTopologyError
from app.sam.client import SUPPORTED_IMAGE_MIME_TYPES
from app.services.image_analysis import (
    AnalyzeImageResult,
    ConfirmAndVerifyResult,
    PhysicalConfirmation,
    UnknownGearIdError,
    analyze_image,
    confirm_and_verify,
)

router = APIRouter(prefix="/image-analysis", tags=["image-analysis"])


def get_sam_provider() -> SAMPerceptionProvider:
    """Constructs a real, SAM-3.1-backed provider.

    Deliberately NOT constructed at module import time: building a real
    ``SAMClient`` requires ``MODEL_API_KEY`` to already be set, and importing
    this module (e.g. via ``app.main``) must never fail just because that
    key is absent. Tests override this dependency with a fake provider --
    see ``app.dependency_overrides``.
    """
    return SAMPerceptionProvider()


@router.post("/analyze", response_model=AnalyzeImageResult)
async def analyze_uploaded_image(
    image: UploadFile = File(...),
    prompt: str = Form(default="gear"),
    provider: SAMPerceptionProvider = Depends(get_sam_provider),
) -> AnalyzeImageResult:
    """Image upload -> SAM -> PerceptionResult + missing-information issues.

    Accepts only what SAM itself supports (JPEG/PNG), validated by content
    type before anything is read. Calls the exact same ``analyze_image``
    function the test suite calls -- no perception or boundary logic is
    duplicated here.
    """
    if image.content_type not in SUPPORTED_IMAGE_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported image content type {image.content_type!r}; "
                f"supported types: {sorted(SUPPORTED_IMAGE_MIME_TYPES)}."
            ),
        )
    image_bytes = await image.read()
    request = ImagePerceptionRequest(
        prompt=prompt, image_bytes=image_bytes, image_mime_type=image.content_type
    )
    return analyze_image(provider, request)


class ConfirmAndVerifyRequest(BaseModel):
    """The round-tripped perception state (as returned by ``/analyze``) plus
    the user's explicit physical confirmation. No session id and no stored
    state -- the frontend simply resends the perception payload it was
    already given.
    """

    perception: PerceptionResult
    confirmation: PhysicalConfirmation


@router.post("/confirm", response_model=ConfirmAndVerifyResult)
def confirm_and_verify_physical_system(
    request: ConfirmAndVerifyRequest,
) -> ConfirmAndVerifyResult:
    """Confirmation -> evidence boundary -> deterministic physics (or refusal).

    Calls the exact same ``confirm_and_verify`` function the test suite
    calls, which itself only calls ``build_physical_system`` and
    ``run_physical_system_experiment`` -- no boundary or physics logic is
    duplicated here.
    """
    try:
        return confirm_and_verify(request.perception, request.confirmation)
    except UnknownGearIdError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UnsupportedTopologyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
