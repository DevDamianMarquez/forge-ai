"""Live smoke test for the Meta Model API connection (Muse Spark).

This is NOT a pytest test. It lives outside backend/tests (pytest.ini
restricts testpaths to "tests") and is deliberately not named test_*.py as
extra insurance against ever being auto-discovered.

Run it manually, and only once MODEL_API_KEY is set in your own local,
untracked environment (e.g. a real .env you have not committed):

    cd backend
    python scripts/meta_connection_check.py

If MODEL_API_KEY is not set, this reports that the live check was skipped
and exits 0 -- it never fails a build and is never run as part of pytest.
It never prints the API key.
"""

from __future__ import annotations

import os
import sys

# Allow running this script directly without installing the package: add
# backend/ (one level up from backend/scripts/) to sys.path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.meta_model import MetaModelClient, MissingModelApiKeyError  # noqa: E402


def main() -> int:
    if not os.environ.get("MODEL_API_KEY"):
        print("MODEL_API_KEY is not set -- skipping live Meta Model API smoke test.")
        return 0

    try:
        client = MetaModelClient()
    except MissingModelApiKeyError as exc:
        print(f"Meta Model API configuration error: {exc}")
        return 1

    try:
        response = client.send(
            messages=[
                {"role": "system", "content": "Reply with exactly: pong"},
                {"role": "user", "content": "ping"},
            ],
            tools=[],
        )
    except Exception as exc:  # pragma: no cover - live network call, not run by pytest
        print(f"Live Meta Model API request failed: {exc}")
        return 1

    print(f"Live Meta Model API request succeeded. Model replied: {response.content!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
