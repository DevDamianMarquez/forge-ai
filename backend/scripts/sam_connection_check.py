"""Live smoke test for the SAM 3.1 connection via the Meta Model API.

This is NOT a pytest test. It lives outside backend/tests (pytest.ini
restricts testpaths to "tests") and is deliberately not named test_*.py as
extra insurance against ever being auto-discovered.

Run it manually, and only once MODEL_API_KEY is set in your own local,
untracked environment (e.g. a real .env you have not committed), and only
with a local image path you supply explicitly:

    cd backend
    python scripts/sam_connection_check.py path/to/image.png [prompt]

If MODEL_API_KEY is not set, this reports that the live check was skipped
and exits 0 -- it never fails a build and is never run as part of pytest.
It never prints the API key, and never embeds an image path or credential
in this file. It makes exactly one SAM analysis call.
"""

from __future__ import annotations

import mimetypes
import os
import sys

# Allow running this script directly without installing the package: add
# backend/ (one level up from backend/scripts/) to sys.path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.sam.client import SAMClient, SUPPORTED_IMAGE_MIME_TYPES  # noqa: E402
from app.services.meta_model import MissingModelApiKeyError  # noqa: E402


def main(argv: list[str]) -> int:
    if not os.environ.get("MODEL_API_KEY"):
        print("MODEL_API_KEY is not set -- skipping live SAM 3.1 smoke test.")
        return 0

    if not argv:
        print("Usage: python scripts/sam_connection_check.py <image-path> [prompt]")
        return 1

    image_path = argv[0]
    prompt = argv[1] if len(argv) > 1 else "object"

    mime_type, _ = mimetypes.guess_type(image_path)
    if mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
        print(f"Unsupported or undetected image type for {image_path!r}: {mime_type!r}")
        return 1

    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
    except OSError as exc:
        print(f"Could not read image file: {exc}")
        return 1

    try:
        client = SAMClient()
    except MissingModelApiKeyError as exc:
        print(f"SAM client configuration error: {exc}")
        return 1

    try:
        result = client.analyze_image(
            prompt, image_bytes=image_bytes, image_mime_type=mime_type
        )
    except Exception as exc:  # pragma: no cover - live network call, not run by pytest
        # Print only the exception type, never str(exc): some SDK error
        # messages echo back request content, which could include our
        # base64 image data URL -- that must never reach stdout/logs.
        print(f"Live SAM 3.1 request failed: {type(exc).__name__}")
        return 1

    print(f"Live SAM 3.1 request succeeded. Parsed {len(result.segmentations)} segmentation(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
