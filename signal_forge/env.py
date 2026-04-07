from __future__ import annotations

import os
from pathlib import Path

_ENV_LOADED = False
_LOADED_ENV_PATH: Path | None = None


def _resolve_env_path() -> Path:
    env_path = os.getenv("SIGNAL_FORGE_ENV_FILE")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return (Path(__file__).resolve().parent.parent / ".env").resolve()


def load_repo_env() -> None:
    global _ENV_LOADED, _LOADED_ENV_PATH
    candidate = _resolve_env_path()
    if _ENV_LOADED and _LOADED_ENV_PATH == candidate:
        return

    _LOADED_ENV_PATH = candidate
    if not candidate.exists():
        _ENV_LOADED = True
        return

    try:
        for raw_line in candidate.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value
    finally:
        _ENV_LOADED = True
