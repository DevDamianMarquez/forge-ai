"""Tests for the Meta Model API client wrapper. No real API calls are made:

client construction never performs network I/O, so these only check
configuration behavior (missing-key error, key sourcing).
"""

from __future__ import annotations

import pytest

from app.services.meta_model import MetaModelClient, MissingModelApiKeyError


def test_importing_meta_model_module_never_requires_a_key():
    # This module was already imported above at collection time; if that
    # required a real key, this test file would not have collected at all.
    import app.services.meta_model  # noqa: F401, PLC0415


def test_constructing_real_client_without_key_raises_clear_error(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    with pytest.raises(MissingModelApiKeyError):
        MetaModelClient()


def test_constructing_real_client_with_explicit_key_does_not_raise(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    client = MetaModelClient(api_key="not-a-real-key")
    assert client is not None


def test_constructing_real_client_reads_key_from_environment(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "not-a-real-key")

    client = MetaModelClient()
    assert client is not None
