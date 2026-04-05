from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonDataCache:
    """Lightweight JSON cache wrapper for normalized market data payloads."""

    def load(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        data = payload.get("data")
        return data if isinstance(data, dict) else None

    def save(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
