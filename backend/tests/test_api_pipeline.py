"""Tests for POST /api/v1/pipeline/run-fixture.

Purely deterministic -- no Muse, no Meta API, no network. This is an
explicit development/demo endpoint; its output must never be mistaken for
real image-based perception.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_run_fixture_endpoint_simple_gear_pair():
    response = client.post("/api/v1/pipeline/run-fixture", json={"fixture_id": "simple_gear_pair"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["experiment"]["experiment"]["result"] == 400.0
    assert [entry["stage"] for entry in body["trace"]] == [
        "perception",
        "model_build",
        "topology",
        "experiment",
    ]


def test_run_fixture_endpoint_compound_gear_train():
    response = client.post("/api/v1/pipeline/run-fixture", json={"fixture_id": "compound_gear_train"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["experiment"]["experiment"]["metrics"]["gear_ratio"] == 9.0


def test_run_fixture_endpoint_uncertain_gear_pair_stops_at_model_build():
    response = client.post("/api/v1/pipeline/run-fixture", json={"fixture_id": "uncertain_gear_pair"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "refused_at_model_build"
    assert body["experiment"] is None
    assert len(body["build_result"]["issues"]) > 0
    assert [entry["stage"] for entry in body["trace"]] == ["perception", "model_build"]


def test_run_fixture_endpoint_rejects_unknown_fixture_cleanly():
    response = client.post("/api/v1/pipeline/run-fixture", json={"fixture_id": "not_a_real_fixture"})

    assert response.status_code == 404


def test_all_endpoints_remain_registered():
    spec = client.get("/openapi.json").json()
    assert "/api/v1/experiments/gear-train" in spec["paths"]
    assert "/api/v1/experiments/physical-system" in spec["paths"]
    assert "/api/v1/forge/analyze" in spec["paths"]
    assert "/api/v1/perception/build-physical-system" in spec["paths"]
    assert "/api/v1/pipeline/run-fixture" in spec["paths"]
