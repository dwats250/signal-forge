from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


CACHE_MAX_AGE = timedelta(hours=24)
REPO_ROOT = Path(__file__).resolve().parents[2]
SYMBOL_CACHE_PATH = REPO_ROOT / "data" / "cache.json"


def _coerce_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _is_fresh(timestamp: object, *, now: datetime | None = None) -> bool:
    parsed = _coerce_datetime(timestamp)
    if parsed is None:
        return False
    reference = now or datetime.now(timezone.utc)
    return reference - parsed <= CACHE_MAX_AGE


def _load_symbol_payload(path: Path = SYMBOL_CACHE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_cache(
    symbol: str,
    value: Any,
    timestamp: str | datetime,
    *,
    path: Path = SYMBOL_CACHE_PATH,
) -> None:
    payload = _load_symbol_payload(path)
    iso_timestamp = _coerce_datetime(timestamp)
    payload[symbol] = {
        "timestamp": (iso_timestamp or datetime.now(timezone.utc)).isoformat(),
        "value": value,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_cached(symbol: str, *, path: Path = SYMBOL_CACHE_PATH) -> dict[str, Any] | None:
    payload = _load_symbol_payload(path)
    entry = payload.get(symbol)
    if not isinstance(entry, dict):
        return None
    timestamp = entry.get("timestamp")
    if not _is_fresh(timestamp):
        return None
    value = entry.get("value")
    if value is None:
        return None
    return {
        "symbol": symbol,
        "timestamp": str(timestamp),
        "value": value,
        "source": "cache",
    }


class JsonDataCache:
    """JSON cache wrapper for normalized market data payloads and symbol cache access."""

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

    def save_symbol(self, symbol: str, value: Any, timestamp: str | datetime, *, path: Path = SYMBOL_CACHE_PATH) -> None:
        save_cache(symbol, value, timestamp, path=path)

    def load_symbol(self, symbol: str, *, path: Path = SYMBOL_CACHE_PATH) -> dict[str, Any] | None:
        return load_cached(symbol, path=path)

