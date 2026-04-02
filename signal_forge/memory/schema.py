from __future__ import annotations

from datetime import datetime, timezone


def build_memory_record(reading: object, classification: object) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": classification.pair,  # type: ignore[attr-defined]
        "signal": classification.signal,  # type: ignore[attr-defined]
        "divergence": classification.divergence,  # type: ignore[attr-defined]
        "context": classification.explanation,  # type: ignore[attr-defined]
    }
