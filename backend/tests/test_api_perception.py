"""Tests for POST /api/v1/perception/build-physical-system.

Purely deterministic -- no Muse, no Meta API, no network.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _observed(value, status, confidence=1.0, source="user"):
    return {"value": value, "source": source, "confidence": confidence, "status": status}


def _confirmed_shaft(shaft_id: str) -> dict:
    return {"id": shaft_id, "source": "user", "confidence": 1.0, "status": "confirmed"}


def _confirmed_gear(gear_id: str, teeth: int, shaft_id: str) -> dict:
    return {
        "id": gear_id,
        "source": "user",
        "confidence": 1.0,
        "status": "confirmed",
        "teeth": _observed(teeth, "confirmed"),
        "shaft_id": _observed(shaft_id, "confirmed"),
    }


def _simple_pair_payload() -> dict:
    return {
        "shafts": [_confirmed_shaft("shaft-a"), _confirmed_shaft("shaft-b")],
        "gears": [_confirmed_gear("gear1", 20, "shaft-a"), _confirmed_gear("gear2", 60, "shaft-b")],
        "meshes": [
            {"gear_a_id": "gear1", "gear_b_id": "gear2", "source": "user", "confidence": 1.0, "status": "confirmed"}
        ],
        "input_shaft_id": _observed("shaft-a", "confirmed"),
        "input_rpm": _observed(1200, "confirmed"),
    }


def test_build_physical_system_endpoint_succeeds_for_fully_confirmed_system():
    response = client.post("/api/v1/perception/build-physical-system", json=_simple_pair_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["physical_system"] is not None
    assert body["issues"] == []
    assert "shaft:shaft-a" in body["accepted_observations"]


def test_build_physical_system_endpoint_rejects_inferred_tooth_count_with_422():
    payload = _simple_pair_payload()
    payload["gears"][0]["teeth"] = _observed(20, "inferred", confidence=0.99)

    response = client.post("/api/v1/perception/build-physical-system", json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert any(issue["code"] == "unconfirmed_value" for issue in detail)


def test_existing_physical_system_endpoint_remains_unchanged():
    payload = {
        "shafts": [{"id": "shaft-a"}, {"id": "shaft-b"}],
        "gears": [
            {"id": "gear1", "teeth": 20, "shaft_id": "shaft-a"},
            {"id": "gear2", "teeth": 60, "shaft_id": "shaft-b"},
        ],
        "meshes": [{"gear_a_id": "gear1", "gear_b_id": "gear2"}],
        "input_shaft_id": "shaft-a",
        "input_rpm": 1200,
    }

    response = client.post("/api/v1/experiments/physical-system", json=payload)

    assert response.status_code == 200
    assert response.json()["experiment"]["result"] == 400.0


def test_existing_gear_train_and_forge_endpoints_still_registered():
    spec = client.get("/openapi.json").json()
    assert "/api/v1/experiments/gear-train" in spec["paths"]
    assert "/api/v1/forge/analyze" in spec["paths"]
    assert "/api/v1/experiments/physical-system" in spec["paths"]
    assert "/api/v1/perception/build-physical-system" in spec["paths"]
