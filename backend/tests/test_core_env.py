"""Tests for the backend/.env bootstrap loader (app.core.env).

Never touches the user's real backend/.env and never makes a network call
-- every test here uses a throwaway temporary .env file with a fake,
obviously-not-real credential value.
"""

from __future__ import annotations

import os

import pytest

from app.core.env import load_backend_env
from app.services.meta_model import MetaModelClient, MissingModelApiKeyError


def _write_fake_env(tmp_path, value: str):
    env_file = tmp_path / ".env"
    env_file.write_text(f"MODEL_API_KEY={value}\n", encoding="utf-8")
    return env_file


# --- A. MODEL_API_KEY can be loaded from a temporary .env source ---------


def test_load_backend_env_loads_key_from_a_temporary_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    env_file = _write_fake_env(tmp_path, "fake-test-key-from-dotenv")

    loaded = load_backend_env(env_file)

    assert loaded is True
    assert os.environ["MODEL_API_KEY"] == "fake-test-key-from-dotenv"


def test_metamodelclient_can_construct_using_a_key_loaded_from_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    env_file = _write_fake_env(tmp_path, "fake-test-key-from-dotenv")

    load_backend_env(env_file)
    client = MetaModelClient()

    assert client is not None


# --- B. An already-existing MODEL_API_KEY is NOT overwritten -------------


def test_load_backend_env_never_overrides_an_existing_environment_variable(monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_API_KEY", "shell-provided-value")
    env_file = _write_fake_env(tmp_path, "different-dotenv-value")

    load_backend_env(env_file)

    assert os.environ["MODEL_API_KEY"] == "shell-provided-value"


# --- C. Missing MODEL_API_KEY still produces the existing safe error -----


def test_missing_env_file_is_not_an_error_and_key_stays_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    nonexistent_path = tmp_path / "does-not-exist.env"

    loaded = load_backend_env(nonexistent_path)

    assert loaded is False
    assert "MODEL_API_KEY" not in os.environ


def test_metamodelclient_still_raises_clear_error_when_key_is_missing_everywhere(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    nonexistent_path = tmp_path / "does-not-exist.env"

    load_backend_env(nonexistent_path)

    with pytest.raises(MissingModelApiKeyError):
        MetaModelClient()
