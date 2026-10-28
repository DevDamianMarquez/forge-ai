"""Minimal Meta Model API (Muse Spark) client wrapper for FORGE.

Canonical config for this milestone (Meta Global AI Developer Hackathon):
    SDK:      the official OpenAI Python SDK (``from openai import OpenAI``)
    Base URL: https://api.meta.ai/v1
    Model:    muse-spark-1.3
    Auth:     MODEL_API_KEY -- the SDK does not read this automatically, so
              it is passed explicitly when constructing the client.

FORGE uses only the Meta Model API. This is not a generic multi-provider
abstraction; it exists to (1) configure that one client correctly and (2) be
trivially injectable/mockable, so the pytest suite never performs a real
Meta API call. Anything that needs to talk to Muse Spark depends on the
``MuseSparkClient`` protocol below, not on this concrete class.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

from openai import OpenAI

DEFAULT_BASE_URL = "https://api.meta.ai/v1"
DEFAULT_MODEL = "muse-spark-1.3"


class MissingModelApiKeyError(RuntimeError):
    """Raised when MODEL_API_KEY is not set and a real Meta client is needed.

    Importing this module, or any module that depends on it, never raises
    this -- only constructing a real ``MetaModelClient`` without a key does.
    """


@dataclass(frozen=True)
class ToolCall:
    """One tool call Muse Spark requested, with arguments already parsed."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class MuseResponse:
    """One normalized Muse Spark turn: a final answer, tool calls, or both."""

    content: str | None
    tool_calls: list[ToolCall]


class MuseSparkClient(Protocol):
    """The minimal interface the orchestration layer needs from a Muse client.

    Both the real ``MetaModelClient`` and any test fake implement just this
    one method, so tests never need to know anything about the OpenAI SDK.
    """

    def send(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> MuseResponse: ...


class MetaModelClient:
    """The real Meta Model API client, talking to muse-spark-1.3 over the OpenAI SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("MODEL_API_KEY", "")
        if not key:
            raise MissingModelApiKeyError(
                "MODEL_API_KEY is not set. Add it to your local .env (see "
                ".env.example) before constructing a real MetaModelClient."
            )
        self._model = model
        self._client = OpenAI(api_key=key, base_url=base_url)

    def send(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> MuseResponse:
        """Send one turn (the full conversation so far) to Muse Spark."""
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=tools,
        )
        message = response.choices[0].message
        tool_calls = [
            ToolCall(
                id=call.id,
                name=call.function.name,
                arguments=json.loads(call.function.arguments or "{}"),
            )
            for call in (message.tool_calls or [])
        ]
        return MuseResponse(content=message.content, tool_calls=tool_calls)
