"""A real, SAM-3.1-backed PerceptionProvider.

THIS IS REAL PERCEPTION, BUT NOT PHYSICAL TRUTH. Every ``PerceivedGear``
built here has ``source=VISION_MODEL`` and ``status=OBSERVED`` -- SAM
visually detected something matching the given prompt, nothing more. It
never supplies a tooth count, a shaft assignment, a gear mesh, an input
shaft, or an RPM: none of those are fabricated here, they are left
entirely absent (``None`` / empty) so that
``app.perception.builder.build_physical_system`` correctly refuses to
build a runnable ``PhysicalSystem`` from SAM output alone.

Confidence is carried through unchanged from SAM's own bounding-box score
when present, and left ``None`` when SAM gave none -- it is never used
here (or anywhere downstream) to promote a detection to ``CONFIRMED``.
Confidence is metadata, not verification, no matter how high it is.

Implements the same ``PerceptionProvider`` contract as
``FixturePerceptionProvider`` (see ``app.perception.providers.base``): one
``analyze`` method, zero changes required anywhere downstream (the
evidence boundary, ``PhysicalSystem``, the topology compiler, the physics
engine, and ``app.services.physical_pipeline`` are all untouched by this
module). It takes an ``ImagePerceptionRequest`` rather than a
``fixture_id`` -- a different, appropriate request shape for a different
kind of provider, exactly as anticipated by that model's own docstring.
"""

from __future__ import annotations

from app.models.perception import (
    ImagePerceptionRequest,
    ObservationSource,
    ObservationStatus,
    PerceivedGear,
    PerceptionResult,
)
from app.sam.client import SAMClient
from app.sam.models import SAMSegmentationResult

_SOURCE = ObservationSource.VISION_MODEL
_STATUS = ObservationStatus.OBSERVED


def _segmentation_id(frame_index: int, object_index: int) -> str:
    """A stable, lightweight identifier traceable back to the exact SAM
    segmentation that produced this perceived object (e.g. "sam-f0-o1" for
    frame 0, object 1). Carries no geometry or mask payload itself -- just
    enough to answer "which SAM detection became this PerceivedGear?".
    """
    return f"sam-f{frame_index}-o{object_index}"


def convert_sam_result_to_perception(
    sam_result: SAMSegmentationResult, *, label: str = "gear (SAM-detected)"
) -> PerceptionResult:
    """Convert raw SAM segmentation evidence into a PerceptionResult.

    Deterministic and side-effect free: no network access, no AI call, no
    randomness, never mutates ``sam_result``. Each segmentation becomes one
    ``PerceivedGear`` with ``source=VISION_MODEL``, ``status=OBSERVED``,
    and ``confidence`` taken directly from SAM's own bounding-box
    confidence (``None`` if SAM gave none -- never defaulted to a number).
    ``teeth`` and ``shaft_id`` are always ``None``: SAM has no concept of
    either. ``shafts``, ``meshes``, ``input_shaft_id``, and ``input_rpm``
    are always empty/``None``: none of those are visually observable from
    a single image at all, and this module never infers or fabricates them.
    """
    gears = [
        PerceivedGear(
            id=_segmentation_id(seg.frame_index, seg.object_index),
            label=label,
            source=_SOURCE,
            confidence=seg.bounding_box.confidence,
            status=_STATUS,
            teeth=None,
            shaft_id=None,
        )
        for seg in sam_result.segmentations
    ]

    notes = [
        f"SAM visually observed {len(gears)} object(s) matching the prompt; "
        "their tooth counts, shaft assignments, and any gear mesh between "
        "them are unknown and require explicit confirmation before any "
        "physics can run."
    ]
    if not gears:
        notes.append("SAM returned zero detections for this image/prompt.")

    return PerceptionResult(
        shafts=[],
        gears=gears,
        meshes=[],
        input_shaft_id=None,
        input_rpm=None,
        output_shaft_id=None,
        notes=notes,
    )


class SAMPerceptionProvider:
    """Image + prompt -> PerceptionResult, backed by a real SAM 3.1 call.

    ``client`` must be injected in tests (a fake implementing
    ``analyze_image``) -- constructing a real ``SAMClient`` requires
    ``MODEL_API_KEY`` and is never done implicitly by this class's tests.
    """

    def __init__(self, client: SAMClient | None = None) -> None:
        self._client = client if client is not None else SAMClient()

    def analyze(self, request: ImagePerceptionRequest) -> PerceptionResult:
        sam_result = self._client.analyze_image(
            request.prompt,
            image_url=request.image_url,
            image_bytes=request.image_bytes,
            image_mime_type=request.image_mime_type,
        )
        return convert_sam_result_to_perception(sam_result)
