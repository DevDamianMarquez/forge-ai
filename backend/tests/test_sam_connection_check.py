"""Focused test for the SAM connection-check script's failure-path safety.

Tests only the one defect fixed during the Milestone 6B pre-live review: a
failed live SAM request must never print the raw exception message, since
some SDK error messages echo back request content, which could include our
base64 image data URL. No real SAM/network call is made here -- SAMClient
is replaced with a fake that raises immediately.
"""

from __future__ import annotations

import scripts.sam_connection_check as sam_connection_check


class _ExplodingClient:
    def __init__(self, *args, **kwargs):
        pass

    def analyze_image(self, *args, **kwargs):
        raise RuntimeError("leaked-base64-payload-marker-should-never-print")


def test_failed_live_request_never_prints_the_raw_exception_message(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("MODEL_API_KEY", "fake-key")
    monkeypatch.setattr(sam_connection_check, "SAMClient", _ExplodingClient)

    image_path = tmp_path / "photo.png"
    image_path.write_bytes(b"\x89PNG-fake-bytes")

    exit_code = sam_connection_check.main([str(image_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "leaked-base64-payload-marker-should-never-print" not in captured.out
    assert "RuntimeError" in captured.out
