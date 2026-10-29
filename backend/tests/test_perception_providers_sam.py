"""Tests for the SAM -> FORGE perception bridge (Milestone 6C).

CENTRAL INVARIANT UNDER TEST: SAM DETECTED != PHYSICALLY CONFIRMED. Every
input here is a synthetic, hand-built ``SAMSegmentationResult`` -- no real
SAM/Muse/network call is made anywhere in this file.
"""

from __future__ import annotations

from app.models.perception import (
    ObservationSource,
    ObservationStatus,
    ObservedValue,
    PerceivedGearMesh,
    PerceivedShaft,
    ImagePerceptionRequest,
)
from app.perception.builder import build_physical_system
from app.perception.providers.sam import SAMPerceptionProvider, convert_sam_result_to_perception
from app.sam.models import SAMBoundingBox, SAMMask, SAMSegmentation, SAMSegmentationResult


def _box(confidence: float | None = None, **overrides) -> SAMBoundingBox:
    defaults = dict(x1=1, y1=2, x2=3, y2=4, width=10, height=10, confidence=confidence)
    defaults.update(overrides)
    return SAMBoundingBox(**defaults)


def _mask() -> SAMMask:
    return SAMMask(x=0, y=0, encoding="lossless", encoded_data="1,~a")


def _two_gear_result(confidences: tuple[float | None, float | None] = (None, None)) -> SAMSegmentationResult:
    return SAMSegmentationResult(
        segmentations=[
            SAMSegmentation(
                frame_index=0, object_index=0, bounding_box=_box(confidences[0]), mask=_mask()
            ),
            SAMSegmentation(
                frame_index=0, object_index=1, bounding_box=_box(confidences[1]), mask=_mask()
            ),
        ],
        raw_output="<0f>0<|box;...|><|mask;...|>,1<|box;...|><|mask;...|>",
    )


# --- A. two SAM gear segmentations -> two perceived visual objects --------


def test_two_segmentations_become_two_perceived_gears():
    result = convert_sam_result_to_perception(_two_gear_result())

    assert len(result.gears) == 2


# --- B. source is VISION_MODEL ----------------------------------------------


def test_perceived_gears_have_vision_model_source():
    result = convert_sam_result_to_perception(_two_gear_result())

    assert all(gear.source == ObservationSource.VISION_MODEL for gear in result.gears)


# --- C. status is OBSERVED --------------------------------------------------


def test_perceived_gears_have_observed_status():
    result = convert_sam_result_to_perception(_two_gear_result())

    assert all(gear.status == ObservationStatus.OBSERVED for gear in result.gears)


# --- D. high confidence does not become CONFIRMED --------------------------


def test_high_confidence_segmentation_still_stays_observed_not_confirmed():
    result = convert_sam_result_to_perception(_two_gear_result(confidences=(0.99, 0.999999)))

    for gear in result.gears:
        assert gear.status == ObservationStatus.OBSERVED
        assert gear.status != ObservationStatus.CONFIRMED


def test_confidence_is_carried_through_unchanged():
    result = convert_sam_result_to_perception(_two_gear_result(confidences=(0.99, 0.42)))

    confidences = {gear.id: gear.confidence for gear in result.gears}
    assert confidences["sam-f0-o0"] == 0.99
    assert confidences["sam-f0-o1"] == 0.42


# --- E. missing SAM confidence remains representable -----------------------


def test_missing_sam_confidence_stays_none_not_fabricated():
    result = convert_sam_result_to_perception(_two_gear_result(confidences=(None, None)))

    assert all(gear.confidence is None for gear in result.gears)


# --- F. segmentation traceability preserved ---------------------------------


def test_perceived_gear_id_traces_back_to_its_sam_segmentation():
    sam_result = SAMSegmentationResult(
        segmentations=[
            SAMSegmentation(frame_index=0, object_index=0, bounding_box=_box(), mask=_mask()),
            SAMSegmentation(frame_index=0, object_index=1, bounding_box=_box(), mask=_mask()),
        ],
        raw_output="...",
    )

    result = convert_sam_result_to_perception(sam_result)

    ids = {gear.id for gear in result.gears}
    assert ids == {"sam-f0-o0", "sam-f0-o1"}


def test_full_mask_payload_is_never_copied_into_perception_models():
    sam_result = _two_gear_result()

    result = convert_sam_result_to_perception(sam_result)

    dumped = result.model_dump_json()
    assert "1,~a" not in dumped  # the mask's encoded_data must never appear here


# --- G. no tooth count fabricated -------------------------------------------


def test_teeth_is_never_fabricated():
    result = convert_sam_result_to_perception(_two_gear_result())

    assert all(gear.teeth is None for gear in result.gears)


# --- H. no shaft assignment fabricated --------------------------------------


def test_shaft_id_is_never_fabricated():
    result = convert_sam_result_to_perception(_two_gear_result())

    assert all(gear.shaft_id is None for gear in result.gears)


# --- I. no mesh fabricated ---------------------------------------------------


def test_no_shafts_meshes_input_shaft_or_rpm_are_fabricated():
    result = convert_sam_result_to_perception(_two_gear_result())

    assert result.shafts == []
    assert result.meshes == []
    assert result.input_shaft_id is None
    assert result.input_rpm is None
    assert result.output_shaft_id is None


def test_zero_detections_is_representable_without_fabrication():
    empty_result = SAMSegmentationResult(segmentations=[], raw_output="")

    result = convert_sam_result_to_perception(empty_result)

    assert result.gears == []


# --- J. pure SAM perception cannot cross the evidence boundary -------------


def test_pure_sam_perception_cannot_cross_evidence_boundary_into_physics():
    perception = convert_sam_result_to_perception(_two_gear_result(confidences=(0.99, 0.99)))

    build_result = build_physical_system(perception)

    assert build_result.physical_system is None
    assert len(build_result.issues) > 0


# --- Wiring: SAMPerceptionProvider delegates to the client + converter ----


class _FakeSAMClient:
    def __init__(self, result: SAMSegmentationResult) -> None:
        self._result = result
        self.last_call: dict | None = None

    def analyze_image(self, prompt, *, image_url=None, image_bytes=None, image_mime_type=None):
        self.last_call = {
            "prompt": prompt,
            "image_url": image_url,
            "image_bytes": image_bytes,
            "image_mime_type": image_mime_type,
        }
        return self._result


def test_sam_perception_provider_delegates_to_client_and_converter():
    sam_result = _two_gear_result(confidences=(0.9, None))
    fake_client = _FakeSAMClient(sam_result)
    provider = SAMPerceptionProvider(client=fake_client)
    request = ImagePerceptionRequest(prompt="gear", image_url="https://example.com/photo.png")

    perception = provider.analyze(request)

    assert fake_client.last_call == {
        "prompt": "gear",
        "image_url": "https://example.com/photo.png",
        "image_bytes": None,
        "image_mime_type": None,
    }
    assert perception == convert_sam_result_to_perception(sam_result)


# --- Section 7: confirmation-path contract ----------------------------------


def test_field_level_user_confirmation_is_representable_with_existing_models_alone():
    """Demonstrates the Milestone 6C confirmation-path contract: promoting
    specific SAM-observed fields to CONFIRMED needs no new code and no
    frontend -- just constructing/copying a PerceptionResult with specific
    ObservedValue fields (and gear/mesh existence) swapped to USER-sourced,
    CONFIRMED ones. Once that happens, the existing, unmodified evidence
    boundary accepts it exactly as it would any other confirmed system.
    """
    perception = convert_sam_result_to_perception(_two_gear_result(confidences=(0.9, 0.9)))
    g1, g2 = perception.gears

    confirmed_g1 = g1.model_copy(
        update={
            "status": ObservationStatus.CONFIRMED,
            "source": ObservationSource.USER,
            "teeth": ObservedValue(
                value=20, source=ObservationSource.USER, confidence=1.0, status=ObservationStatus.CONFIRMED
            ),
            "shaft_id": ObservedValue(
                value="shaft-a",
                source=ObservationSource.USER,
                confidence=1.0,
                status=ObservationStatus.CONFIRMED,
            ),
        }
    )
    confirmed_g2 = g2.model_copy(
        update={
            "status": ObservationStatus.CONFIRMED,
            "source": ObservationSource.USER,
            "teeth": ObservedValue(
                value=60, source=ObservationSource.USER, confidence=1.0, status=ObservationStatus.CONFIRMED
            ),
            "shaft_id": ObservedValue(
                value="shaft-b",
                source=ObservationSource.USER,
                confidence=1.0,
                status=ObservationStatus.CONFIRMED,
            ),
        }
    )

    confirmed_perception = perception.model_copy(
        update={
            "shafts": [
                PerceivedShaft(
                    id="shaft-a", source=ObservationSource.USER, confidence=1.0, status=ObservationStatus.CONFIRMED
                ),
                PerceivedShaft(
                    id="shaft-b", source=ObservationSource.USER, confidence=1.0, status=ObservationStatus.CONFIRMED
                ),
            ],
            "gears": [confirmed_g1, confirmed_g2],
            "meshes": [
                PerceivedGearMesh(
                    gear_a_id=g1.id,
                    gear_b_id=g2.id,
                    source=ObservationSource.USER,
                    confidence=1.0,
                    status=ObservationStatus.CONFIRMED,
                )
            ],
            "input_shaft_id": ObservedValue(
                value="shaft-a", source=ObservationSource.USER, confidence=1.0, status=ObservationStatus.CONFIRMED
            ),
            "input_rpm": ObservedValue(
                value=1200.0, source=ObservationSource.USER, confidence=1.0, status=ObservationStatus.CONFIRMED
            ),
        }
    )

    result = build_physical_system(confirmed_perception)

    assert result.issues == []
    assert result.physical_system is not None
