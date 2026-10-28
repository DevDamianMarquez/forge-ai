"""Tests for the single POST /api/v1/experiments/gear-train endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_gear_train_experiment_endpoint_canonical_case():
    payload = {
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

    response = client.post("/api/v1/experiments/gear-train", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["result"] == 400.0
    assert body["unit"] == "rpm"
    assert body["status"] == "success"
    assert body["constraint_results"][0]["passed"] is True


def test_gear_train_experiment_endpoint_constraint_fail():
    payload = {
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
            {"name": "max-output-rpm", "metric": "output_rpm", "operator": "lte", "value": 300}
        ],
    }

    response = client.post("/api/v1/experiments/gear-train", json=payload)

    assert response.status_code == 200
    assert response.json()["constraint_results"][0]["passed"] is False


def test_gear_train_experiment_endpoint_rejects_invalid_teeth():
    payload = {
        "train": {
            "input_rpm": 1200,
            "connections": [
                {
                    "driver": {"id": "driver", "teeth": 0},
                    "driven": {"id": "driven", "teeth": 60},
                }
            ],
        },
        "constraints": [],
    }

    response = client.post("/api/v1/experiments/gear-train", json=payload)

    assert response.status_code == 422


def test_gear_train_experiment_endpoint_rejects_empty_connections():
    payload = {"train": {"input_rpm": 1200, "connections": []}, "constraints": []}

    response = client.post("/api/v1/experiments/gear-train", json=payload)

    assert response.status_code == 422
