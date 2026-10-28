"""A tiny scripted fake Muse client for tests. Never calls the real Meta API."""

from __future__ import annotations

from typing import Any

from app.services.meta_model import MuseResponse


class FakeMuseClient:
    """Returns a pre-scripted sequence of MuseResponse objects, one per `send` call."""

    def __init__(self, responses: list[MuseResponse]) -> None:
        self._responses = list(responses)
        self.sent_messages: list[list[dict[str, Any]]] = []
        self.call_count = 0

    def send(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> MuseResponse:
        self.sent_messages.append(messages)
        self.call_count += 1
        if not self._responses:
            raise AssertionError("FakeMuseClient has no more scripted responses")
        return self._responses.pop(0)
