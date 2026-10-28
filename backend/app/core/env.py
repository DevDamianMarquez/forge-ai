"""Minimal environment bootstrap: load backend/.env, if present.

This is the one place FORGE decides where its local environment file lives
and how it is loaded -- "settings, config loading", as reserved for this
package since the project's original scaffolding. It knows nothing about
Meta, Muse, or any specific variable; it only makes whatever backend/.env
contains available via ``os.environ``, the same way the process's own
shell environment already is. Never logs, prints, or otherwise exposes the
file's contents.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# This file lives at backend/app/core/env.py, so backend/ is three parents up.
DEFAULT_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


def load_backend_env(path: Path | str | None = None) -> bool:
    """Load a .env file into the process environment, if it exists.

    Never overrides a variable the process environment already has --
    anything explicitly set in the shell/process environment remains
    authoritative over whatever the file contains. Returns True if a file
    was found and read, False otherwise (no backend/.env is a normal,
    supported state, not an error).
    """
    target = Path(path) if path is not None else DEFAULT_ENV_PATH
    return load_dotenv(dotenv_path=target, override=False)
