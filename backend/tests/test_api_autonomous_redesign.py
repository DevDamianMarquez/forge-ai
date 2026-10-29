"""Tests for POST /api/v1/forge/autonomous-redesign.

Always overrides the Muse client dependency with a fake -- never calls the
real Meta API.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.forge import get_muse_client
from app.main import app
from app.services.meta_model import MuseResponse, ToolCall
from tests.fakes import FakeMuseClient

TOOL_NAME = "test_gear_design"

STARTING_TRAIN = {
    "input_rpm": 1200,
    "connections": [{"driver": {"id": "input", "teeth": 20}, "driven": {"id": "output", "teeth": 60}}],
}


def teardown_function() -> None:
    app.dependency_overrides.clear()


def _candidate_response(input_teeth: int, output_teeth: int) -> MuseResponse:
    return MuseResponse(
        content=None,
        tool_calls=[
            ToolCall(
                id="call-1",
                name=TOOL_NAME,
                arguments={"input_teeth": input_teeth, "output_teeth": output_teeth},
            )
        ],
    )


def test_autonomous_redesign_endpoint_canonical_fail_then_pass():
    fake = FakeMuseClient([_candidate_response(20, 60), _candidate_response(20, 80)])
    app.dependency_overrides[get_muse_client] = lambda: fake
    client = TestClient(app)

    response = client.post(
        "/api/v1/forge/autonomous-redesign",
        json={"starting_train": STARTING_TRAIN, "objective_max_output_rpm": 300},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "verified"
    assert body["accepted_design"] == {"input_teeth": 20, "output_teeth": 80}
    assert body["final_experiment"]["result"] == 300.0
    assert len(body["attempts"]) == 2
    assert body["attempts"][0]["status"] == "failed"
    assert body["attempts"][1]["status"] == "passed"
    assert [entry["stage"] for entry in body["trace"]][-1] == "design_verified"


def test_autonomous_redesign_endpoint_exhausts_on_all_failing_candidates():
    fake = FakeMuseClient(
        [_candidate_response(20, 60), _candidate_response(20, 65), _candidate_response(20, 70)]
    )
    app.dependency_overrides[get_muse_client] = lambda: fake
    client = TestClient(app)

    response = client.post(
        "/api/v1/forge/autonomous-redesign",
        json={"starting_train": STARTING_TRAIN, "objective_max_output_rpm": 300},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "exhausted"
    assert body["accepted_design"] is None
    assert len(body["attempts"]) == 3


def test_autonomous_redesign_endpoint_rejects_multi_stage_starting_train():
    fake = FakeMuseClient([])
    app.dependency_overrides[get_muse_client] = lambda: fake
    client = TestClient(app)

    multi_stage_train = {
        "input_rpm": 1200,
        "connections": [
            {"driver": {"id": "g1", "teeth": 20}, "driven": {"id": "g2", "teeth": 60}},
            {"driver": {"id": "g3", "teeth": 15}, "driven": {"id": "g4", "teeth": 45}},
        ],
    }

    response = client.post(
        "/api/v1/forge/autonomous-redesign",
        json={"starting_train": multi_stage_train, "objective_max_output_rpm": 300},
    )

    assert response.status_code == 422


def test_autonomous_redesign_endpoint_handles_unknown_tool_without_crashing():
    fake = FakeMuseClient(
        [
            MuseResponse(content=None, tool_calls=[ToolCall(id="c1", name="delete_database", arguments={})]),
            _candidate_response(20, 80),
        ]
    )
    app.dependency_overrides[get_muse_client] = lambda: fake
    client = TestClient(app)

    response = client.post(
        "/api/v1/forge/autonomous-redesign",
        json={"starting_train": STARTING_TRAIN, "objective_max_output_rpm": 300},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["attempts"][0]["status"] == "unknown_tool"
    assert body["status"] == "verified"


def test_autonomous_redesign_endpoint_registered_in_openapi():
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    assert "/api/v1/forge/autonomous-redesign" in spec["paths"]
    assert "/api/v1/forge/analyze" in spec["paths"]


def test_existing_forge_analyze_endpoint_unaffected():
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    assert "/api/v1/experiments/gear-train" in spec["paths"]
    assert "/api/v1/perception/build-physical-system" in spec["paths"]
    assert "/api/v1/pipeline/run-fixture" in spec["paths"]
    assert "/api/v1/image-analysis/analyze" in spec["paths"]
