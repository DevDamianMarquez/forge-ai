"""Raw SAM 3.1 domain models: exactly what the verified Meta documentation
describes, nothing more.

These models hold SAM's raw geometric output only -- box coordinates and
opaque encoded mask data. They carry no semantic meaning, no confirmation
status, and no mechanical properties: no teeth counts, no shaft IDs, no
gear meshes, no RPM. SAM is a visual sensor for FORGE, not a source of
verified mechanical truth. Converting this raw evidence into FORGE's
perception/evidence-boundary models (``app.models.perception``) is
explicitly out of scope for this milestone.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SAMBoundingBox(BaseModel):
    """One detection's box, in the source image's pixel coordinate space.

    ``confidence`` is SAM's own optional score (0.0-1.0) when present --
    this is raw model output, never a FORGE ``ObservationStatus``.
    """

    x1: int
    y1: int
    x2: int
    y2: int
    width: int
    height: int
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class SAMMask(BaseModel):
    """One detection's mask, exactly as SAM encoded it.

    ``encoded_data`` is preserved verbatim. This module never decodes the
    run-length-encoded raster data -- no official Python decoder is
    documented, and decoding it is not required by this milestone.
    ``encoding`` is "lossless" or "one_bit" when the corresponding marker
    (``~`` or ``!``) is present in the data, else "unknown" -- never
    guessed beyond what the data string itself shows.
    """

    x: int
    y: int
    encoding: str
    encoded_data: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class SAMSegmentation(BaseModel):
    """One (frame, object) detection: a box, and a mask if SAM returned one.

    ``mask`` is ``None`` when an object entry carried a box tag but no mask
    tag -- a box-only detection, not a malformed response.
    """

    frame_index: int
    object_index: int
    bounding_box: SAMBoundingBox
    mask: SAMMask | None = None


class SAMSegmentationResult(BaseModel):
    """The fully parsed output of one SAM analysis call.

    ``raw_output`` is the complete collected output text, kept verbatim for
    debugging and test fixtures. It is plain response text only -- never
    anything from the request (no image bytes, no API key).
    """

    segmentations: list[SAMSegmentation] = Field(default_factory=list)
    raw_output: str
