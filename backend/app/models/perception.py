"""Pydantic domain models for FORGE's perception layer (Milestone 3B).

PERCEPTION IS NOT GROUND TRUTH. A future vision/reasoning model may observe
or infer a component, a tooth count, a shaft assignment, or a mesh -- but
none of that is physical evidence until it is explicitly confirmed. These
models hold only what the system currently *believes*; the deterministic
``PhysicalSystem`` in ``app.models.physics`` holds what has actually been
accepted for calculation. ``app.perception.builder`` is the one place that
boundary is crossed, and it is never automatic.

Kept deliberately separate from ``app.models.physics``: that module stays
clean and physics-only, with no notion of confidence or uncertainty at all.
"""

from __future__ import annotations

from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.models.physics import PhysicalSystem

T = TypeVar("T")


class ObservationSource(str, Enum):
    """Where one observation came from."""

    USER = "user"
    VISION_MODEL = "vision_model"
    REASONING_MODEL = "reasoning_model"
    DERIVED = "derived"


class ObservationStatus(str, Enum):
    """Whether an observation may be trusted as physical ground truth.

    Only ``CONFIRMED`` may ever cross into a ``PhysicalSystem`` (see
    ``app.perception.builder``). Nothing else does, no matter how high its
    confidence is -- confidence is metadata, not verification.
    """

    OBSERVED = "observed"
    INFERRED = "inferred"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"


class ObservedValue(BaseModel, Generic[T]):
    """One perceived value: what it is, where it came from, how confident
    the observer is, and whether it has been confirmed.

    Confidence and status are independent. A confidence of 1.0 with status
    "inferred" is still not confirmed; a confidence of 0.6 with status
    "confirmed" is. Only ``status`` decides whether this value may ever
    become deterministic physical ground truth.
    """

    value: T
    source: ObservationSource
    confidence: float = Field(..., ge=0.0, le=1.0)
    status: ObservationStatus


class PerceivedShaft(BaseModel):
    """A shaft the system believes it has identified.

    ``confidence``/``status``/``source`` describe this shaft's existence
    itself -- a shaft has no further sub-attributes uncertain enough to
    need their own observation.
    """

    id: str = Field(..., min_length=1)
    label: str | None = None
    source: ObservationSource
    confidence: float = Field(..., ge=0.0, le=1.0)
    status: ObservationStatus


class PerceivedGear(BaseModel):
    """A gear the system believes it has identified.

    The gear's own existence (``confidence``/``status``/``source``) is
    tracked separately from its attribute values: a gear might be confirmed
    to exist while its tooth count or shaft assignment is still only
    inferred, observed, or unresolved.
    """

    id: str = Field(..., min_length=1)
    label: str | None = None
    source: ObservationSource
    confidence: float = Field(..., ge=0.0, le=1.0)
    status: ObservationStatus
    teeth: ObservedValue[int]
    shaft_id: ObservedValue[str]


class PerceivedGearMesh(BaseModel):
    """A gear mesh the system believes it has identified between two gears."""

    gear_a_id: str = Field(..., min_length=1)
    gear_b_id: str = Field(..., min_length=1)
    source: ObservationSource
    confidence: float = Field(..., ge=0.0, le=1.0)
    status: ObservationStatus


class PerceptionResult(BaseModel):
    """Everything the system currently believes about one mechanical
    system's topology, before any of it is allowed to become deterministic
    physical ground truth.

    Deliberately unvalidated beyond basic field shape: perception may be
    incomplete, contradictory, or low-confidence, and that is fine -- it is
    not yet truth. ``app.perception.builder`` is what decides what (if
    anything) is trustworthy enough to become a ``PhysicalSystem``, which
    still enforces its own full validation on whatever makes it through.
    """

    shafts: list[PerceivedShaft] = Field(default_factory=list)
    gears: list[PerceivedGear] = Field(default_factory=list)
    meshes: list[PerceivedGearMesh] = Field(default_factory=list)
    input_shaft_id: ObservedValue[str]
    input_rpm: ObservedValue[float]
    output_shaft_id: ObservedValue[str] | None = Field(
        default=None,
        description=(
            "Optional: if absent or not confirmed, it is simply omitted from "
            "the built PhysicalSystem -- the topology compiler may still "
            "infer it unambiguously."
        ),
    )
    notes: list[str] = Field(
        default_factory=list, description="Free-text unresolved issues or warnings."
    )


class PerceptionIssueCode(str, Enum):
    """A small, fixed set of reasons a PerceptionResult could not (yet)
    become a PhysicalSystem. Deliberately not exhaustive -- just enough for
    a future UI to explain the refusal clearly.
    """

    UNCONFIRMED_VALUE = "unconfirmed_value"
    MISSING_VALUE = "missing_value"
    REJECTED_VALUE = "rejected_value"
    INVALID_REFERENCE = "invalid_reference"


class PerceptionIssue(BaseModel):
    """One concrete reason a PerceptionResult could not (yet) become a
    PhysicalSystem -- e.g. "FORGE cannot verify this system because Gear G2
    tooth count is inferred, not confirmed."
    """

    code: PerceptionIssueCode
    message: str
    component_id: str | None = None
    field: str | None = None
    status: ObservationStatus | None = None


class PhysicalSystemBuildResult(BaseModel):
    """The outcome of attempting to build a PhysicalSystem from a PerceptionResult.

    If ``issues`` is non-empty, ``physical_system`` is always ``None`` --
    FORGE never partially accepts an uncertain system. ``accepted_observations``
    and ``unresolved_observations`` trace which perceived fields crossed the
    boundary (or were deliberately omitted) on success; this is metadata
    about the build, not part of PhysicalSystem itself, which stays clean
    and deterministic with no notion of confidence or status at all.
    """

    physical_system: PhysicalSystem | None
    accepted_observations: list[str] = Field(default_factory=list)
    unresolved_observations: list[str] = Field(default_factory=list)
    issues: list[PerceptionIssue] = Field(default_factory=list)
