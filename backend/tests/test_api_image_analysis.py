"""Tests for Milestone 7A.1's real-image engineering flow endpoints:

    POST /api/v1/image-analysis/analyze
    POST /api/v1/image-analysis/confirm

No real Meta/SAM call is ever made: every test injects a fake SAM client
(mirroring tests/test_perception_providers_sam.py's ``_FakeSAMClient``) into
a real, unmodified ``SAMPerceptionProvider`` via a FastAPI dependency
override. The provider, the evidence boundary, and the physics engine are
all exercised for real -- only the network-touching SAM transport is faked.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.image_analysis import get_sam_provider
from app.main import app
from app.perception.providers.sam import SAMPerceptionProvider
from app.sam.models import SAMBoundingBox, SAMMask, SAMSegmentation, SAMSegmentationResult

client = TestClient(app)

_SECRET_MASK_MARKER = "TOTALLY-SECRET-MASK-PAYLOAD"


class _FakeSAMClient:
    """Mirrors tests/test_perception_providers_sam.py's fake: records the
    call it received and returns a pre-scripted SAMSegmentationResult. Never
    touches the network."""

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


def _box(confidence: float | None = None) -> SAMBoundingBox:
    return SAMBoundingBox(x1=1, y1=2, x2=3, y2=4, width=10, height=10, confidence=confidence)


def _mask() -> SAMMask:
    return SAMMask(x=0, y=0, encoding="lossless", encoded_data=f"1,~{_SECRET_MASK_MARKER}")


def _two_gear_sam_result(confidences: tuple[float | None, float | None] = (None, None)) -> SAMSegmentationResult:
    return SAMSegmentationResult(
        segmentations=[
            SAMSegmentation(frame_index=0, object_index=0, bounding_box=_box(confidences[0]), mask=_mask()),
            SAMSegmentation(frame_index=0, object_index=1, bounding_box=_box(confidences[1]), mask=_mask()),
        ],
        raw_output="<0f>0<|box;...|><|mask;...|>,1<|box;...|><|mask;...|>",
    )


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    app.dependency_overrides.pop(get_sam_provider, None)


def _override_provider(sam_result: SAMSegmentationResult) -> _FakeSAMClient:
    fake_client = _FakeSAMClient(sam_result)
    app.dependency_overrides[get_sam_provider] = lambda: SAMPerceptionProvider(client=fake_client)
    return fake_client


def _post_analyze(content_type: str = "image/jpeg", filename: str = "photo.jpg"):
    return client.post(
        "/api/v1/image-analysis/analyze",
        files={"image": (filename, b"fake-image-bytes", content_type)},
        data={"prompt": "gear"},
    )


# --- A/B. JPEG and PNG uploads are accepted ---------------------------------


def test_jpeg_upload_is_accepted():
    _override_provider(_two_gear_sam_result())

    response = _post_analyze(content_type="image/jpeg", filename="photo.jpg")

    assert response.status_code == 200


def test_png_upload_is_accepted():
    _override_provider(_two_gear_sam_result())

    response = _post_analyze(content_type="image/png", filename="photo.png")

    assert response.status_code == 200


# --- C. unsupported MIME type is rejected -----------------------------------


def test_unsupported_mime_type_is_rejected():
    _override_provider(_two_gear_sam_result())

    response = _post_analyze(content_type="application/pdf", filename="photo.pdf")

    assert response.status_code == 415


# --- D/E. two SAM detections -> two VISION_MODEL/OBSERVED observations -----


def test_two_gear_sam_result_becomes_two_visual_observations():
    _override_provider(_two_gear_sam_result())

    body = _post_analyze().json()

    gears = body["perception"]["gears"]
    assert len(gears) == 2
    assert all(gear["source"] == "vision_model" for gear in gears)
    assert all(gear["status"] == "observed" for gear in gears)


# --- F. high SAM confidence never confirms physical truth -------------------


def test_high_sam_confidence_does_not_confirm_physical_truth():
    _override_provider(_two_gear_sam_result(confidences=(0.99, 0.999999)))

    body = _post_analyze().json()

    gears = body["perception"]["gears"]
    assert all(gear["status"] == "observed" for gear in gears)
    assert body["build_result"]["physical_system"] is None


# --- G/H. initial build is refused, with useful missing-information issues -


def test_initial_build_is_refused_with_missing_information_issues():
    _override_provider(_two_gear_sam_result())

    body = _post_analyze().json()

    assert body["build_result"]["physical_system"] is None
    issues = body["build_result"]["issues"]
    assert len(issues) > 0
    assert any(issue["code"] == "missing_value" for issue in issues)


# --- I. raw mask payload is never exposed -----------------------------------


def test_raw_mask_payload_is_not_exposed():
    _override_provider(_two_gear_sam_result())

    response = _post_analyze()

    assert _SECRET_MASK_MARKER not in response.text
    assert "raw_output" not in response.json()["perception"]
    assert "encoded_data" not in response.text


# --- VisualDetection: safe bounding-box geometry alongside PerceptionResult -


def test_analyze_response_exposes_visual_detections_with_matching_ids():
    _override_provider(_two_gear_sam_result(confidences=(0.9, None)))

    body = _post_analyze().json()

    detection_ids = {d["id"] for d in body["detections"]}
    gear_ids = {g["id"] for g in body["perception"]["gears"]}
    assert detection_ids == gear_ids == {"sam-f0-o0", "sam-f0-o1"}


def test_visual_detections_carry_safe_bounding_box_and_metadata_only():
    _override_provider(_two_gear_sam_result(confidences=(0.9, None)))

    body = _post_analyze().json()

    for detection in body["detections"]:
        assert detection["bounding_box"] == {
            "x1": 1,
            "y1": 2,
            "x2": 3,
            "y2": 4,
            "width": 10,
            "height": 10,
            "confidence": detection["confidence"],
        }
        assert detection["source"] == "vision_model"
        assert detection["status"] == "observed"
        assert "mask" not in detection
        assert "encoded_data" not in detection


def test_analyze_endpoint_registered_in_openapi():
    spec = client.get("/openapi.json").json()
    assert "/api/v1/image-analysis/analyze" in spec["paths"]
    assert "/api/v1/image-analysis/confirm" in spec["paths"]


# --- Confirmation contract + evidence boundary + physics -------------------


def _confirm_payload(perception: dict, confirmation: dict) -> dict:
    return {"perception": perception, "confirmation": confirmation}


def _analyze_two_gears() -> dict:
    _override_provider(_two_gear_sam_result(confidences=(0.9, 0.9)))
    return _post_analyze().json()["perception"]


# --- J. confirmation marks ONLY the explicitly supplied fields -------------


def test_confirmation_marks_only_explicitly_supplied_fields():
    perception = _analyze_two_gears()
    gear_id = perception["gears"][0]["id"]

    response = client.post(
        "/api/v1/image-analysis/confirm",
        json=_confirm_payload(
            perception,
            {
                "shafts": [],
                "gears": [{"id": gear_id, "teeth": 20}],  # shaft_id/confirmed_exists omitted
                "meshes": [],
            },
        ),
    )

    assert response.status_code == 200
    confirmed_gear = next(g for g in response.json()["perception"]["gears"] if g["id"] == gear_id)
    assert confirmed_gear["teeth"]["status"] == "confirmed"
    assert confirmed_gear["teeth"]["source"] == "user"
    assert confirmed_gear["shaft_id"] is None  # never silently filled in
    # a property confirmation does NOT implicitly confirm existence
    assert confirmed_gear["status"] == "observed"
    assert confirmed_gear["source"] == "vision_model"


def test_explicit_confirmed_exists_confirms_gear_existence():
    perception = _analyze_two_gears()
    gear_id = perception["gears"][0]["id"]

    response = client.post(
        "/api/v1/image-analysis/confirm",
        json=_confirm_payload(
            perception, {"shafts": [], "gears": [{"id": gear_id, "confirmed_exists": True}], "meshes": []}
        ),
    )

    assert response.status_code == 200
    confirmed_gear = next(g for g in response.json()["perception"]["gears"] if g["id"] == gear_id)
    assert confirmed_gear["status"] == "confirmed"
    assert confirmed_gear["source"] == "user"
    assert confirmed_gear["teeth"] is None  # never silently filled in


# --- K. incomplete confirmation remains refused -----------------------------


def test_incomplete_confirmation_remains_refused():
    perception = _analyze_two_gears()
    gear_id = perception["gears"][0]["id"]

    response = client.post(
        "/api/v1/image-analysis/confirm",
        json=_confirm_payload(
            perception,
            {"shafts": [], "gears": [{"id": gear_id, "teeth": 20}], "meshes": []},
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["build_result"]["physical_system"] is None
    assert body["experiment"] is None


def test_property_confirmation_without_existence_still_refused_at_evidence_boundary():
    """confirmed_exists=false + teeth=20 -> existence stays OBSERVED, so the
    evidence boundary must still refuse the whole system, even with every
    other fact (shafts/mesh/RPM) confirmed."""
    perception = _analyze_two_gears()
    g1_id, g2_id = perception["gears"][0]["id"], perception["gears"][1]["id"]

    confirmation = {
        "shafts": [{"id": "shaft-a"}, {"id": "shaft-b"}],
        "gears": [
            {"id": g1_id, "confirmed_exists": False, "teeth": 20, "shaft_id": "shaft-a"},
            {"id": g2_id, "confirmed_exists": True, "teeth": 60, "shaft_id": "shaft-b"},
        ],
        "meshes": [{"gear_a_id": g1_id, "gear_b_id": g2_id}],
        "input_shaft_id": "shaft-a",
        "input_rpm": 1200,
        "output_shaft_id": "shaft-b",
    }

    response = client.post("/api/v1/image-analysis/confirm", json=_confirm_payload(perception, confirmation))

    assert response.status_code == 200
    body = response.json()
    assert body["build_result"]["physical_system"] is None
    assert body["experiment"] is None
    assert any(
        issue["component_id"] == g1_id and issue["field"] == "existence"
        for issue in body["build_result"]["issues"]
    )


# --- L/M/N/O/P. the canonical confirmation builds and runs real physics ----


def test_canonical_confirmation_builds_physical_system_and_runs_physics():
    perception = _analyze_two_gears()
    g1_id, g2_id = perception["gears"][0]["id"], perception["gears"][1]["id"]

    confirmation = {
        "shafts": [{"id": "shaft-a"}, {"id": "shaft-b"}],
        "gears": [
            {"id": g1_id, "confirmed_exists": True, "teeth": 20, "shaft_id": "shaft-a"},
            {"id": g2_id, "confirmed_exists": True, "teeth": 60, "shaft_id": "shaft-b"},
        ],
        "meshes": [{"gear_a_id": g1_id, "gear_b_id": g2_id}],
        "input_shaft_id": "shaft-a",
        "input_rpm": 1200,
        "output_shaft_id": "shaft-b",
    }

    response = client.post(
        "/api/v1/image-analysis/confirm", json=_confirm_payload(perception, confirmation)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["build_result"]["physical_system"] is not None
    assert body["build_result"]["issues"] == []

    experiment = body["experiment"]["experiment"]
    assert experiment["result"] == 400.0  # N
    assert experiment["metrics"]["gear_ratio"] == 3.0  # O
    assert experiment["metrics"]["output_direction"] == -1.0  # P: reversed


def test_confirmation_referencing_unknown_gear_id_is_rejected():
    perception = _analyze_two_gears()

    response = client.post(
        "/api/v1/image-analysis/confirm",
        json=_confirm_payload(
            perception, {"shafts": [], "gears": [{"id": "not-a-real-gear", "teeth": 20}], "meshes": []}
        ),
    )

    assert response.status_code == 422
