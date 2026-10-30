"""Tests for the cheap, static GET /health production readiness check."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200_with_exact_minimal_body():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_works_without_model_api_key(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_never_constructs_a_meta_model_client(monkeypatch):
    import app.services.meta_model as meta_model

    def _fail_if_constructed(*args, **kwargs):
        raise AssertionError("GET /health must never construct a MetaModelClient")

    monkeypatch.setattr(meta_model.MetaModelClient, "__init__", _fail_if_constructed)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_never_constructs_a_sam_client(monkeypatch):
    import app.sam.client as sam_client

    def _fail_if_constructed(*args, **kwargs):
        raise AssertionError("GET /health must never construct a SAMClient")

    monkeypatch.setattr(sam_client.SAMClient, "__init__", _fail_if_constructed)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
