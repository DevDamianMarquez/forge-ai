"""Deterministic orchestration for Milestone 7A.1's real-image engineering flow.

Two things live here, both pure sequencing/data-transformation -- no physics
arithmetic and no physical inference anywhere in this module:

  1. ``analyze_image``: SAMPerceptionProvider -> PerceptionResult -> the
     evidence boundary (``build_physical_system``), so a caller immediately
     learns what SAM visually observed *and* what is still missing before
     physics can run. Mirrors ``app.services.physical_pipeline``'s
     orchestration style, but for a real image instead of a fixture, and
     stopping before topology/physics since nothing is confirmed yet.

  2. ``apply_confirmation`` / ``confirm_and_verify``: the smallest explicit
     USER confirmation contract for this milestone
     (``PhysicalConfirmation``), and the pipeline that folds it into a
     PerceptionResult, then calls the exact same ``build_physical_system``
     and ``run_physical_system_experiment`` the rest of FORGE already uses.
     Confirmation data becomes a ``PhysicalSystem`` only by crossing the
     evidence boundary -- never by direct construction.

No Muse, no Meta, no network, no database. State moves between the two
halves of this flow by the caller round-tripping the ``PerceptionResult``
it was already given -- nothing is persisted here.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.perception import (
    ImagePerceptionRequest,
    ObservationSource,
    ObservationStatus,
    ObservedValue,
    PerceivedGearMesh,
    PerceivedShaft,
    PerceptionResult,
    PhysicalSystemBuildResult,
)
from app.models.physics import PhysicalSystemExperimentResult
from app.perception.builder import build_physical_system
from app.perception.providers.sam import SAMPerceptionProvider
from app.physics.topology import run_physical_system_experiment
from app.sam.models import SAMBoundingBox, SAMSegmentationResult

_USER = ObservationSource.USER
_CONFIRMED = ObservationStatus.CONFIRMED


class VisualDetection(BaseModel):
    """Safe, SAM-specific visual detection geometry for one segmentation.

    Deliberately NOT part of ``PerceivedGear`` (``app.models.perception``):
    that model is provider-independent and must never carry SAM-specific
    geometry. This DTO exists only so a frontend can draw the box SAM
    actually found, without widening the provider-independent evidence
    model to know about boxes at all.

    ``id`` always equals the ``PerceivedGear.id`` built from the same SAM
    segmentation (see ``app.perception.providers.sam.segmentation_id``), so
    a caller can correlate one drawn box with its perception/evidence
    entry. Carries only the segmentation's bounding box (plain coordinates
    + confidence) -- never its mask's ``encoded_data``, and never
    ``SAMSegmentationResult.raw_output``.
    """

    id: str
    frame_index: int
    object_index: int
    bounding_box: SAMBoundingBox
    confidence: float | None = None
    source: ObservationSource
    status: ObservationStatus


def _build_visual_detections(
    sam_result: SAMSegmentationResult, perception: PerceptionResult
) -> list[VisualDetection]:
    """Pair each SAM segmentation with the PerceivedGear built from it.

    ``convert_sam_result_to_perception`` (``app.perception.providers.sam``)
    builds exactly one ``PerceivedGear`` per segmentation, in the same
    order, so zipping positionally is exact -- ``strict=True`` turns any
    future divergence into an immediate error rather than a silent
    mismatch.
    """
    return [
        VisualDetection(
            id=gear.id,
            frame_index=segmentation.frame_index,
            object_index=segmentation.object_index,
            bounding_box=segmentation.bounding_box,
            confidence=gear.confidence,
            source=gear.source,
            status=gear.status,
        )
        for segmentation, gear in zip(sam_result.segmentations, perception.gears, strict=True)
    ]


class AnalyzeImageResult(BaseModel):
    """What one real-image analysis produced.

    ``perception`` holds only what SAM visually observed (see
    ``app.perception.providers.sam`` -- always ``VISION_MODEL``/``OBSERVED``,
    never fabricated teeth/shaft/mesh/RPM data) and stays provider-
    independent. ``detections`` carries the SAM-specific bounding-box
    geometry for the same observations, safely, alongside it -- never
    merged into ``perception`` itself. ``build_result`` reuses the existing
    evidence-boundary output directly: its ``physical_system`` is ``None``
    and its ``issues`` explain exactly what remains unconfirmed, unless the
    provider itself already returned fully-confirmed data (never true for a
    vision-model provider).
    """

    perception: PerceptionResult
    detections: list[VisualDetection]
    build_result: PhysicalSystemBuildResult


def analyze_image(
    provider: SAMPerceptionProvider, request: ImagePerceptionRequest
) -> AnalyzeImageResult:
    """SAMClient -> SAMPerceptionProvider -> PerceptionResult -> evidence boundary.

    Performs no physics and no physical inference, and never auto-confirms
    anything -- it only reports what ``build_physical_system`` says is
    missing, reusing that function's own issues rather than duplicating any
    validation logic.
    """
    perception, sam_result = provider.analyze_with_raw_result(request)
    build_result = build_physical_system(perception)
    detections = _build_visual_detections(sam_result, perception)
    return AnalyzeImageResult(
        perception=perception, detections=detections, build_result=build_result
    )


class ShaftConfirmation(BaseModel):
    """A shaft the USER explicitly confirms exists.

    SAM never proposes shafts at all (a single static image carries no shaft
    information), so every shaft in this flow is introduced by the user.
    Unlike ``GearConfirmation``, a shaft has no separate confirmable
    attribute besides its own existence (``label`` is a free-text
    convenience, not a physical fact requiring confirmation) -- so entry
    presence here unambiguously means "the user confirms this shaft
    exists," with no implicit-confirmation ambiguity to resolve.
    """

    id: str = Field(..., min_length=1)
    label: str | None = None


class GearConfirmation(BaseModel):
    """One gear's user-confirmed physical facts, matched by ``id`` against an
    existing ``PerceivedGear`` in the perception state being confirmed.

    Existence and attributes are confirmed independently and explicitly:

    - ``confirmed_exists=True`` confirms the gear itself exists (source=USER,
      status=CONFIRMED on the gear's own existence field).
    - ``teeth``/``shaft_id`` confirm only that specific attribute when given.

    Supplying a property WITHOUT ``confirmed_exists=True`` never confirms
    existence -- e.g. ``{"id": "g1", "teeth": 20}`` confirms only the tooth
    count; the gear's existence remains whatever perception already had
    (VISION_MODEL/OBSERVED for a SAM detection), and the evidence boundary
    correctly still refuses the system until existence is confirmed too.
    An omitted attribute field is left exactly as perception already had
    it, never silently filled in.
    """

    id: str = Field(..., min_length=1)
    confirmed_exists: bool = False
    teeth: int | None = Field(default=None, gt=0)
    shaft_id: str | None = Field(default=None, min_length=1)


class MeshConfirmation(BaseModel):
    """A gear mesh the USER explicitly confirms exists between two gears.

    Like ``ShaftConfirmation``, a mesh has no separate confirmable attribute
    besides its own existence (its two gear ids are its identity, not an
    independent physical fact) -- so entry presence here unambiguously means
    "the user confirms this mesh exists."
    """

    gear_a_id: str = Field(..., min_length=1)
    gear_b_id: str = Field(..., min_length=1)


class PhysicalConfirmation(BaseModel):
    """The smallest explicit USER confirmation contract for Milestone 7A.1.

    Every field here is an engineering fact the user is asserting directly
    -- never derived from SAM confidence, never defaulted. Every field
    defaults to empty/``None``, meaning "the user confirmed nothing here";
    that is different from confirming a false/zero value, and
    ``apply_confirmation`` never conflates the two.
    """

    shafts: list[ShaftConfirmation] = Field(default_factory=list)
    gears: list[GearConfirmation] = Field(default_factory=list)
    meshes: list[MeshConfirmation] = Field(default_factory=list)
    input_shaft_id: str | None = None
    input_rpm: float | None = Field(default=None, gt=0)
    output_shaft_id: str | None = None


class UnknownGearIdError(ValueError):
    """Raised when a ``GearConfirmation`` names a gear id absent from the
    perception state it is being applied to. Never silently dropped -- that
    would hide a real integration mismatch between what the frontend is
    confirming and what perception actually contains.
    """


def _confirmed(value: object, confidence: float = 1.0) -> ObservedValue:
    return ObservedValue(value=value, source=_USER, confidence=confidence, status=_CONFIRMED)


def apply_confirmation(
    perception: PerceptionResult, confirmation: PhysicalConfirmation
) -> PerceptionResult:
    """Fold explicit USER confirmation data into `perception`.

    Produces a new ``PerceptionResult`` -- never a ``PhysicalSystem``. The
    evidence boundary (``build_physical_system``) is the only thing allowed
    to attempt that next. Deterministic and side-effect free: never mutates
    `perception`. Only the fields a confirmation entry explicitly supplies
    become ``source=USER``/``status=CONFIRMED``; everything else is carried
    through completely unchanged.
    """
    known_gear_ids = {gear.id for gear in perception.gears}
    for gear_confirmation in confirmation.gears:
        if gear_confirmation.id not in known_gear_ids:
            raise UnknownGearIdError(
                f"confirmation references gear id {gear_confirmation.id!r}, which "
                "is not in the perception state being confirmed"
            )

    shafts_by_id = {shaft.id: shaft for shaft in perception.shafts}
    for shaft_confirmation in confirmation.shafts:
        shafts_by_id[shaft_confirmation.id] = PerceivedShaft(
            id=shaft_confirmation.id,
            label=shaft_confirmation.label,
            source=_USER,
            confidence=1.0,
            status=_CONFIRMED,
        )

    gear_confirmations_by_id = {gc.id: gc for gc in confirmation.gears}
    gears = []
    for gear in perception.gears:
        gear_confirmation = gear_confirmations_by_id.get(gear.id)
        if gear_confirmation is None:
            gears.append(gear)
            continue
        update: dict[str, object] = {}
        if gear_confirmation.confirmed_exists:
            update["status"] = _CONFIRMED
            update["source"] = _USER
        if gear_confirmation.teeth is not None:
            update["teeth"] = _confirmed(gear_confirmation.teeth)
        if gear_confirmation.shaft_id is not None:
            update["shaft_id"] = _confirmed(gear_confirmation.shaft_id)
        gears.append(gear.model_copy(update=update) if update else gear)

    meshes_by_pair = {
        frozenset((mesh.gear_a_id, mesh.gear_b_id)): mesh for mesh in perception.meshes
    }
    for mesh_confirmation in confirmation.meshes:
        pair = frozenset((mesh_confirmation.gear_a_id, mesh_confirmation.gear_b_id))
        meshes_by_pair[pair] = PerceivedGearMesh(
            gear_a_id=mesh_confirmation.gear_a_id,
            gear_b_id=mesh_confirmation.gear_b_id,
            source=_USER,
            confidence=1.0,
            status=_CONFIRMED,
        )

    update: dict[str, object] = {
        "shafts": list(shafts_by_id.values()),
        "gears": gears,
        "meshes": list(meshes_by_pair.values()),
    }
    if confirmation.input_shaft_id is not None:
        update["input_shaft_id"] = _confirmed(confirmation.input_shaft_id)
    if confirmation.input_rpm is not None:
        update["input_rpm"] = _confirmed(confirmation.input_rpm)
    if confirmation.output_shaft_id is not None:
        update["output_shaft_id"] = _confirmed(confirmation.output_shaft_id)

    return perception.model_copy(update=update)


class ConfirmAndVerifyResult(BaseModel):
    """The outcome of applying confirmation data and attempting to cross the
    evidence boundary.

    ``experiment`` is populated only when ``build_result.physical_system``
    is not ``None`` -- by construction, no confirmed ``PhysicalSystem``
    means no physics evidence.
    """

    perception: PerceptionResult
    build_result: PhysicalSystemBuildResult
    experiment: PhysicalSystemExperimentResult | None = None


def confirm_and_verify(
    perception: PerceptionResult, confirmation: PhysicalConfirmation
) -> ConfirmAndVerifyResult:
    """USER confirmation -> PerceptionResult -> evidence boundary -> physics.

    Performs no physics or topology computation itself -- every number still
    comes from ``app.physics.topology.run_physical_system_experiment``
    (Milestone 1's engine, unchanged), called only if
    ``build_physical_system`` actually produced a ``PhysicalSystem``.
    """
    confirmed_perception = apply_confirmation(perception, confirmation)
    build_result = build_physical_system(confirmed_perception)
    experiment = None
    if build_result.physical_system is not None:
        experiment = run_physical_system_experiment(build_result.physical_system)
    return ConfirmAndVerifyResult(
        perception=confirmed_perception, build_result=build_result, experiment=experiment
    )
