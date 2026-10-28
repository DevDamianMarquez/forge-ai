"""Tests for POST /api/v1/forge/analyze.

Always overrides the Muse client dependency with a fake -- never calls the
real Meta API -- and confirms the existing Milestone 1 endpoint is unaffected.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.forge import get_muse_client
from app.main import app
from app.services.forge_tools import GEAR_TRAIN_EXPERIMENT_TOOL_NAME
from app.services.meta_model import MuseResponse, ToolCall
from tests.fakes import FakeMuseClient

VALID_ARGUMENTS = {
    "train": {
        "input_rpm": 1200,
        "connections": [
            {
                "driver": {"id": "driver", "teeth": 20},
                "driven": {"id": "driven", "teeth": 60},
            }
        ],
    },
    "constraints": [
        {"name": "max-output-rpm", "metric": "output_rpm", "operator": "lte", "value": 500}
    ],
}


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_forge_analyze_endpoint_returns_canonical_result_and_evidence():
    fake = FakeMuseClient(
        [
            MuseResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name=GEAR_TRAIN_EXPERIMENT_TOOL_NAME,
                        arguments=VALID_ARGUMENTS,
                    )
                ],
            ),
            MuseResponse(content="Output RPM is 400, within the 500 RPM limit.", tool_calls=[]),
        ]
    )
    app.dependency_overrides[get_muse_client] = lambda: fake
    client = TestClient(app)

    response = client.post(
        "/api/v1/forge/analyze",
        json={
            "objective": "Verify whether this gear transmission keeps the output speed below 500 RPM.",
            "system_data": VALID_ARGUMENTS,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["answer"] == "Output RPM is 400, within the 500 RPM limit."
    assert len(body["experiments"]) == 1
    assert body["experiments"][0]["result"] == 400.0
    assert body["experiments"][0]["constraint_results"][0]["passed"] is True
    assert body["tool_rounds"] == 1


def test_forge_analyze_endpoint_handles_no_tool_call():
    fake = FakeMuseClient([MuseResponse(content="No calculation needed.", tool_calls=[])])
    app.dependency_overrides[get_muse_client] = lambda: fake
    client = TestClient(app)

    response = client.post(
        "/api/v1/forge/analyze",
        json={"objective": "Just explain.", "system_data": {}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["experiments"] == []


def test_existing_gear_train_endpoint_is_unaffected_by_forge_router():
    client = TestClient(app)
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
