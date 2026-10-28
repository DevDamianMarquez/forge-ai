"""Tests for POST /api/v1/experiments/physical-system.

This endpoint is purely deterministic -- no Muse, no Meta API, no network.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _simple_pair_payload() -> dict:
    return {
        "shafts": [{"id": "shaft-a"}, {"id": "shaft-b"}],
        "gears": [
            {"id": "gear1", "teeth": 20, "shaft_id": "shaft-a"},
            {"id": "gear2", "teeth": 60, "shaft_id": "shaft-b"},
        ],
        "meshes": [{"gear_a_id": "gear1", "gear_b_id": "gear2"}],
        "input_shaft_id": "shaft-a",
        "input_rpm": 1200,
    }


def test_physical_system_endpoint_canonical_pair():
    response = client.post("/api/v1/experiments/physical-system", json=_simple_pair_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["experiment"]["result"] == 400.0
    assert body["experiment"]["status"] == "success"
    assert body["topology"]["input_shaft_id"] == "shaft-a"
    assert body["topology"]["output_shaft_id"] == "shaft-b"
    assert len(body["topology"]["gear_train"]["connections"]) == 1


def test_physical_system_endpoint_rejects_invalid_shape_with_422():
    payload = _simple_pair_payload()
    payload["gears"][1]["shaft_id"] = "no-such-shaft"

    response = client.post("/api/v1/experiments/physical-system", json=payload)

    assert response.status_code == 422


def test_physical_system_endpoint_rejects_unsupported_topology_with_422():
    payload = _simple_pair_payload()
    payload["shafts"].append({"id": "shaft-isolated"})
    payload["output_shaft_id"] = "shaft-isolated"

    response = client.post("/api/v1/experiments/physical-system", json=payload)

    assert response.status_code == 422
    assert "not reachable" in response.json()["detail"]


def test_existing_gear_train_endpoint_remains_unchanged():
    payload = {
        "train": {
            "input_rpm": 1200,
            "connections": [
                {"driver": {"id": "driver", "teeth": 20}, "driven": {"id": "driven", "teeth": 60}}
            ],
        },
        "constraints": [],
    }

    response = client.post("/api/v1/experiments/gear-train", json=payload)

    assert response.status_code == 200
    assert response.json()["result"] == 400.0
