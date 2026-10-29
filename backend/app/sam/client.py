"""Thin SAM 3.1 client: image + prompt -> SAMSegmentationResult.

Canonical config, verified during Milestone 6A:
    Base URL: https://api.meta.ai/v1 (same host as the Muse Spark client)
    Model:    sam-3.1
    Auth:     MODEL_API_KEY (same single credential, same backend/.env
              loading as app.services.meta_model)
    Protocol: the OpenAI SDK's Responses API
              (``client.responses.stream(...)``)

Deliberately NOT built on ``MuseSparkClient`` -- SAM's call shape
(Responses API) is different from Muse Spark's
(``chat.completions.create(...)``), so reusing that protocol would be
wrong, not simpler. See app.services.meta_model for that client; this one
is independent.

Network transport is injected (``SAMResponseTransport``) so tests never
need to perform a real HTTP call -- only ``OpenAISAMTransport`` touches the
network, and it is never constructed by the test suite.

Never logs the API key, full image payloads, or request headers.
"""

from __future__ import annotations

import base64
import os
from typing import Any, Protocol

from app.core.env import load_backend_env
from app.sam.models import SAMSegmentationResult
from app.sam.parser import parse_sam_output
from app.services.meta_model import MissingModelApiKeyError

load_backend_env()

DEFAULT_BASE_URL = "https://api.meta.ai/v1"
DEFAULT_MODEL = "sam-3.1"

# The narrowest reliable set for this milestone's demo path. Not a stand-in
# for an undocumented Meta size/format limit -- Meta does not document
# image size/resolution limits (see Milestone 6A report); this allowlist
# only restricts the two formats FORGE actually intends to send.
SUPPORTED_IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png"})


class SAMResponseTransport(Protocol):
    """Anything that can turn one built Responses-API request into the full
    collected ``output_text`` SAM streamed back."""

    def collect_output_text(self, request: dict[str, Any]) -> str: ...


class OpenAISAMTransport:
    """The real transport: calls SAM 3.1 over the OpenAI SDK's Responses API."""

    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL) -> None:
        from openai import OpenAI  # local import: never required to build a fake transport

        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def collect_output_text(self, request: dict[str, Any]) -> str:
        chunks: list[str] = []
        with self._client.responses.stream(**request) as stream:
            for event in stream:
                if event.type == "response.output_text.delta":
                    chunks.append(event.delta)
        return "".join(chunks)


class SAMClient:
    """Image + short concept prompt -> parsed, raw SAM segmentation evidence.

    This client never builds a PerceptionResult, never assigns an
    ObservationStatus, and never infers teeth counts, shaft IDs, gear
    meshes, or RPM -- it only returns what SAM itself returned, parsed.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        transport: SAMResponseTransport | None = None,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("MODEL_API_KEY", "")
        if not key:
            raise MissingModelApiKeyError(
                "MODEL_API_KEY is not set. Add it to your local .env (see "
                ".env.example) before constructing a real SAMClient."
            )
        self._model = model
        self._transport = (
            transport if transport is not None else OpenAISAMTransport(key, base_url)
        )

    def analyze_image(
        self,
        prompt: str,
        *,
        image_url: str | None = None,
        image_bytes: bytes | None = None,
        image_mime_type: str | None = None,
    ) -> SAMSegmentationResult:
        """Send one image + one short concept prompt to SAM, and parse the result.

        Exactly one of ``image_url`` or (``image_bytes`` and
        ``image_mime_type``) must be given. Local bytes are converted to a
        base64 data URL internally -- never written to disk or logged.
        """
        resolved_image_url = _resolve_image_url(image_url, image_bytes, image_mime_type)
        request = {
            "model": self._model,
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": resolved_image_url},
                    ],
                }
            ],
        }
        raw_output = self._transport.collect_output_text(request)
        return parse_sam_output(raw_output)


def _resolve_image_url(
    image_url: str | None, image_bytes: bytes | None, image_mime_type: str | None
) -> str:
    has_url = image_url is not None
    has_bytes = image_bytes is not None

    if has_url and has_bytes:
        raise ValueError("Pass either image_url or image_bytes, not both.")
    if not has_url and not has_bytes:
        raise ValueError("One of image_url or image_bytes is required.")

    if has_url:
        return image_url

    if image_mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
        raise ValueError(
            f"Unsupported image_mime_type {image_mime_type!r}; "
            f"supported types: {sorted(SUPPORTED_IMAGE_MIME_TYPES)}."
        )
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{image_mime_type};base64,{encoded}"
