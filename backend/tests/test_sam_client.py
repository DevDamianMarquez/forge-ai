"""Tests for the SAM 3.1 client (app.sam.client). No real API calls are made:

every test here injects a ``FakeSAMTransport`` instead of
``OpenAISAMTransport``, so no network I/O and no OpenAI SDK call ever
occurs during this suite.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.sam.client import DEFAULT_MODEL, SAMClient
from app.sam.parser import parse_sam_output
from app.services.meta_model import MissingModelApiKeyError

_RAW_OUTPUT = "<0f>0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|><|mask;x=0;y=0;data=1,~a|>"


class FakeSAMTransport:
    """Records the request it was given and returns a scripted raw output."""

    def __init__(self, raw_output: str = _RAW_OUTPUT) -> None:
        self._raw_output = raw_output
        self.last_request: dict[str, Any] | None = None
        self.call_count = 0

    def collect_output_text(self, request: dict[str, Any]) -> str:
        self.last_request = request
        self.call_count += 1
        return self._raw_output


# --- I. SAM client uses sam-3.1 by default ----------------------------------


def test_sam_client_uses_sam_3_1_model_by_default():
    transport = FakeSAMTransport()
    client = SAMClient(api_key="fake-key", transport=transport)

    client.analyze_image("gear", image_url="https://example.com/photo.png")

    assert DEFAULT_MODEL == "sam-3.1"
    assert transport.last_request["model"] == "sam-3.1"


def test_sam_client_uses_explicit_model_when_given():
    transport = FakeSAMTransport()
    client = SAMClient(api_key="fake-key", model="sam-3.1-custom", transport=transport)

    client.analyze_image("gear", image_url="https://example.com/photo.png")

    assert transport.last_request["model"] == "sam-3.1-custom"


# --- J. existing MODEL_API_KEY environment behavior remains correct --------


def test_constructing_sam_client_without_key_raises_clear_error(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    with pytest.raises(MissingModelApiKeyError):
        SAMClient(transport=FakeSAMTransport())


def test_constructing_sam_client_with_explicit_key_does_not_raise(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    client = SAMClient(api_key="not-a-real-key", transport=FakeSAMTransport())

    assert client is not None


def test_constructing_sam_client_reads_key_from_environment(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "not-a-real-key")

    client = SAMClient(transport=FakeSAMTransport())

    assert client is not None


def test_missing_key_never_constructs_a_real_network_transport(monkeypatch):
    # If the key check ran after transport construction, this would try to
    # build a real OpenAI client and could behave differently; assert the
    # error happens with no transport supplied at all, i.e. before any
    # transport (fake or real) is ever touched.
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    with pytest.raises(MissingModelApiKeyError):
        SAMClient()


# --- K. client passes parsed output through the deterministic parser ------


def test_client_result_matches_direct_parser_call_on_same_raw_output():
    transport = FakeSAMTransport(_RAW_OUTPUT)
    client = SAMClient(api_key="fake-key", transport=transport)

    client_result = client.analyze_image("gear", image_url="https://example.com/photo.png")
    direct_result = parse_sam_output(_RAW_OUTPUT)

    assert client_result == direct_result


def test_client_raises_sam_parse_error_for_malformed_transport_output():
    from app.sam.parser import SAMParseError

    malformed = "<0f>0<|mask;x=0;y=0;data=1,~a|>"  # mask with no box: incomplete
    transport = FakeSAMTransport(malformed)
    client = SAMClient(api_key="fake-key", transport=transport)

    with pytest.raises(SAMParseError):
        client.analyze_image("gear", image_url="https://example.com/photo.png")


# --- Image input handling ---------------------------------------------------


def test_image_url_is_passed_through_unmodified():
    transport = FakeSAMTransport()
    client = SAMClient(api_key="fake-key", transport=transport)

    client.analyze_image("gear", image_url="https://example.com/photo.png")

    content = transport.last_request["input"][0]["content"]
    image_part = next(part for part in content if part["type"] == "input_image")
    assert image_part["image_url"] == "https://example.com/photo.png"


def test_prompt_text_is_passed_through_as_input_text():
    transport = FakeSAMTransport()
    client = SAMClient(api_key="fake-key", transport=transport)

    client.analyze_image("yellow school bus", image_url="https://example.com/photo.png")

    content = transport.last_request["input"][0]["content"]
    text_part = next(part for part in content if part["type"] == "input_text")
    assert text_part["text"] == "yellow school bus"


def test_image_bytes_are_converted_to_a_base64_data_url():
    transport = FakeSAMTransport()
    client = SAMClient(api_key="fake-key", transport=transport)

    client.analyze_image(
        "gear", image_bytes=b"\x89PNG-fake-bytes", image_mime_type="image/png"
    )

    content = transport.last_request["input"][0]["content"]
    image_part = next(part for part in content if part["type"] == "input_image")
    assert image_part["image_url"].startswith("data:image/png;base64,")


def test_unsupported_mime_type_is_rejected_locally():
    transport = FakeSAMTransport()
    client = SAMClient(api_key="fake-key", transport=transport)

    with pytest.raises(ValueError):
        client.analyze_image(
            "gear", image_bytes=b"not-an-image", image_mime_type="application/pdf"
        )


def test_passing_both_image_url_and_image_bytes_is_rejected():
    transport = FakeSAMTransport()
    client = SAMClient(api_key="fake-key", transport=transport)

    with pytest.raises(ValueError):
        client.analyze_image(
            "gear",
            image_url="https://example.com/photo.png",
            image_bytes=b"abc",
            image_mime_type="image/png",
        )


def test_passing_neither_image_url_nor_image_bytes_is_rejected():
    transport = FakeSAMTransport()
    client = SAMClient(api_key="fake-key", transport=transport)

    with pytest.raises(ValueError):
        client.analyze_image("gear")
