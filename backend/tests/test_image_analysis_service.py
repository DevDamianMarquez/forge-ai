"""Unit tests for app.services.image_analysis: analyze_image, VisualDetection,
apply_confirmation, and confirm_and_verify.

Purely deterministic -- no Muse, no Meta, no network. Uses the same
synthetic SAM segmentation evidence as tests/test_perception_providers_sam.py.
"""

from __future__ import annotations

import pytest

from app.models.perception import (
    ImagePerceptionRequest,
    ObservationSource,
    ObservationStatus,
)
from app.perception.providers.sam import SAMPerceptionProvider, convert_sam_result_to_perception
from app.sam.models import SAMBoundingBox, SAMMask, SAMSegmentation, SAMSegmentationResult
from app.services.image_analysis import (
    GearConfirmation,
    MeshConfirmation,
    PhysicalConfirmation,
    ShaftConfirmation,
    UnknownGearIdError,
    analyze_image,
    apply_confirmation,
    confirm_and_verify,
)

_SECRET_MASK_MARKER = "TOTALLY-SECRET-MASK-PAYLOAD"


def _box(confidence: float | None = None, **overrides) -> SAMBoundingBox:
    defaults = dict(x1=1, y1=2, x2=3, y2=4, width=10, height=10, confidence=confidence)
    defaults.update(overrides)
    return SAMBoundingBox(**defaults)


def _mask() -> SAMMask:
    return SAMMask(x=0, y=0, encoding="lossless", encoded_data=f"1,~{_SECRET_MASK_MARKER}")


def _two_gear_sam_result(
    confidences: tuple[float | None, float | None] = (None, None)
) -> SAMSegmentationResult:
    return SAMSegmentationResult(
        segmentations=[
            SAMSegmentation(
                frame_index=0, object_index=0, bounding_box=_box(confidences[0], x1=1), mask=_mask()
            ),
            SAMSegmentation(
                frame_index=0, object_index=1, bounding_box=_box(confidences[1], x1=5), mask=_mask()
            ),
        ],
        raw_output="<0f>0<|box;...|><|mask;...|>,1<|box;...|><|mask;...|>",
    )


class _FakeSAMClient:
    def __init__(self, result: SAMSegmentationResult) -> None:
        self._result = result

    def analyze_image(self, prompt, *, image_url=None, image_bytes=None, image_mime_type=None):
        return self._result


def _perception():
    return convert_sam_result_to_perception(_two_gear_sam_result())


def _analyze(sam_result: SAMSegmentationResult):
    provider = SAMPerceptionProvider(client=_FakeSAMClient(sam_result))
    request = ImagePerceptionRequest(prompt="gear", image_url="https://example.com/x.png")
    return analyze_image(provider, request)


# --- analyze_image: pure orchestration, no physics, no auto-confirmation --


def test_analyze_image_returns_perception_and_refused_build_result():
    result = _analyze(_two_gear_sam_result())

    assert len(result.perception.gears) == 2
    assert result.build_result.physical_system is None
    assert len(result.build_result.issues) > 0


def test_analyze_image_performs_no_physics_arithmetic():
    """analyze_image must never produce an experiment -- only the confirm
    half of the flow may call run_physical_system_experiment."""
    result = _analyze(_two_gear_sam_result())

    assert not hasattr(result, "experiment")


# --- VisualDetection: safe geometry alongside the provider-independent PerceptionResult


def test_two_segmentations_produce_two_visual_detections():
    result = _analyze(_two_gear_sam_result())

    assert len(result.detections) == 2


def test_detection_ids_correspond_to_perceived_gear_ids():
    result = _analyze(_two_gear_sam_result())

    detection_ids = {d.id for d in result.detections}
    gear_ids = {g.id for g in result.perception.gears}
    assert detection_ids == gear_ids == {"sam-f0-o0", "sam-f0-o1"}


def test_bounding_boxes_are_preserved_correctly():
    result = _analyze(_two_gear_sam_result())

    boxes_by_id = {d.id: d.bounding_box for d in result.detections}
    assert boxes_by_id["sam-f0-o0"].x1 == 1
    assert boxes_by_id["sam-f0-o1"].x1 == 5
    for box in boxes_by_id.values():
        assert (box.y1, box.x2, box.y2, box.width, box.height) == (2, 3, 4, 10, 10)


def test_detection_confidence_is_preserved_including_none():
    result = _analyze(_two_gear_sam_result(confidences=(0.87, None)))

    confidences = {d.id: d.confidence for d in result.detections}
    assert confidences["sam-f0-o0"] == 0.87
    assert confidences["sam-f0-o1"] is None


def test_detection_source_remains_vision_model():
    result = _analyze(_two_gear_sam_result())

    assert all(d.source == ObservationSource.VISION_MODEL for d in result.detections)


def test_detection_status_remains_observed():
    result = _analyze(_two_gear_sam_result())

    assert all(d.status == ObservationStatus.OBSERVED for d in result.detections)


def test_detection_payload_never_carries_mask_or_raw_output():
    result = _analyze(_two_gear_sam_result())

    dumped = result.model_dump_json()
    assert _SECRET_MASK_MARKER not in dumped
    assert "encoded_data" not in dumped
    assert "raw_output" not in dumped


# --- apply_confirmation: existence confirmation is explicit, not implicit -


def test_property_confirmation_without_confirmed_exists_does_not_confirm_existence():
    perception = _perception()
    g1_id = perception.gears[0].id

    confirmation = PhysicalConfirmation(gears=[GearConfirmation(id=g1_id, teeth=20)])
    updated = apply_confirmation(perception, confirmation)

    g1 = next(g for g in updated.gears if g.id == g1_id)
    assert g1.teeth.value == 20
    assert g1.teeth.status == ObservationStatus.CONFIRMED
    assert g1.teeth.source == ObservationSource.USER
    assert g1.shaft_id is None  # never silently filled in
    # existence was never explicitly confirmed, so it must remain untouched
    assert g1.status == ObservationStatus.OBSERVED
    assert g1.source == ObservationSource.VISION_MODEL


def test_explicit_confirmed_exists_confirms_gear_existence():
    perception = _perception()
    g1_id = perception.gears[0].id

    confirmation = PhysicalConfirmation(gears=[GearConfirmation(id=g1_id, confirmed_exists=True)])
    updated = apply_confirmation(perception, confirmation)

    g1 = next(g for g in updated.gears if g.id == g1_id)
    assert g1.status == ObservationStatus.CONFIRMED
    assert g1.source == ObservationSource.USER
    assert g1.teeth is None  # never silently filled in


def test_evidence_boundary_still_refuses_when_only_property_confirmed_without_existence():
    """confirmed_exists=False + teeth=20 -> existence stays OBSERVED, so the
    evidence boundary must still refuse the system."""
    perception = _perception()
    g1_id = perception.gears[0].id

    confirmation = PhysicalConfirmation(
        gears=[GearConfirmation(id=g1_id, confirmed_exists=False, teeth=20)]
    )
    result = confirm_and_verify(perception, confirmation)

    assert result.build_result.physical_system is None
    assert any(
        issue.component_id == g1_id and issue.field == "existence" for issue in result.build_result.issues
    )


def test_apply_confirmation_leaves_unmentioned_gears_untouched():
    perception = _perception()
    g1_id = perception.gears[0].id
    g2_before = perception.gears[1]

    confirmation = PhysicalConfirmation(gears=[GearConfirmation(id=g1_id, teeth=20)])
    updated = apply_confirmation(perception, confirmation)

    g2_after = next(g for g in updated.gears if g.id == g2_before.id)
    assert g2_after == g2_before
    assert g2_after.status == ObservationStatus.OBSERVED


def test_apply_confirmation_adds_confirmed_shafts_and_meshes():
    perception = _perception()
    g1_id, g2_id = perception.gears[0].id, perception.gears[1].id

    confirmation = PhysicalConfirmation(
        shafts=[ShaftConfirmation(id="shaft-a"), ShaftConfirmation(id="shaft-b")],
        gears=[
            GearConfirmation(id=g1_id, confirmed_exists=True, teeth=20, shaft_id="shaft-a"),
            GearConfirmation(id=g2_id, confirmed_exists=True, teeth=60, shaft_id="shaft-b"),
        ],
        meshes=[MeshConfirmation(gear_a_id=g1_id, gear_b_id=g2_id)],
        input_shaft_id="shaft-a",
        input_rpm=1200,
        output_shaft_id="shaft-b",
    )
    updated = apply_confirmation(perception, confirmation)

    assert {s.id for s in updated.shafts} == {"shaft-a", "shaft-b"}
    assert all(s.status == ObservationStatus.CONFIRMED for s in updated.shafts)
    assert len(updated.meshes) == 1
    assert updated.meshes[0].status == ObservationStatus.CONFIRMED
    assert updated.input_shaft_id.value == "shaft-a"
    assert updated.input_rpm.value == 1200
    assert updated.output_shaft_id.value == "shaft-b"


def test_apply_confirmation_never_mutates_original_perception():
    perception = _perception()
    g1_id = perception.gears[0].id
    original_status = perception.gears[0].status

    apply_confirmation(perception, PhysicalConfirmation(gears=[GearConfirmation(id=g1_id, teeth=20)]))

    assert perception.gears[0].status == original_status
    assert perception.gears[0].teeth is None


def test_apply_confirmation_rejects_unknown_gear_id():
    perception = _perception()

    with pytest.raises(UnknownGearIdError):
        apply_confirmation(
            perception, PhysicalConfirmation(gears=[GearConfirmation(id="not-a-real-gear", teeth=20)])
        )


# --- confirm_and_verify: evidence boundary + real physics, canonical demo -


def _canonical_confirmation(g1_id: str, g2_id: str) -> PhysicalConfirmation:
    """The canonical complete demo confirmation: explicit existence for both
    gears and both shafts, their teeth/shaft assignments, the mesh, and the
    system-level input/output facts. Everything here becomes
    source=USER/status=CONFIRMED."""
    return PhysicalConfirmation(
        shafts=[ShaftConfirmation(id="shaft-a"), ShaftConfirmation(id="shaft-b")],
        gears=[
            GearConfirmation(id=g1_id, confirmed_exists=True, teeth=20, shaft_id="shaft-a"),
            GearConfirmation(id=g2_id, confirmed_exists=True, teeth=60, shaft_id="shaft-b"),
        ],
        meshes=[MeshConfirmation(gear_a_id=g1_id, gear_b_id=g2_id)],
        input_shaft_id="shaft-a",
        input_rpm=1200,
        output_shaft_id="shaft-b",
    )


def test_confirm_and_verify_refuses_incomplete_confirmation():
    perception = _perception()
    g1_id = perception.gears[0].id

    result = confirm_and_verify(
        perception, PhysicalConfirmation(gears=[GearConfirmation(id=g1_id, confirmed_exists=True, teeth=20)])
    )

    assert result.build_result.physical_system is None
    assert result.experiment is None


def test_confirm_and_verify_canonical_demo_produces_expected_physics():
    perception = _perception()
    g1_id, g2_id = perception.gears[0].id, perception.gears[1].id

    result = confirm_and_verify(perception, _canonical_confirmation(g1_id, g2_id))

    assert result.build_result.physical_system is not None
    assert result.build_result.issues == []
    assert result.experiment is not None
    experiment = result.experiment.experiment
    assert experiment.result == 400.0
    assert experiment.metrics["gear_ratio"] == 3.0
    assert experiment.metrics["output_direction"] == -1.0
