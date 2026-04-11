"""
Layer 10 — Audit Log

Appends one JSON Lines record per pipeline run to logs/audit.jsonl.
Never overwrites. Never truncates.

Schema is intentionally flat for grep/jq compatibility.

Note: AuditLogger stub preserved for V1 pipeline.py import compatibility.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_LOG_PATH = Path("logs/audit.jsonl")


# ---------------------------------------------------------------------------
# Record schema
# ---------------------------------------------------------------------------

@dataclass
class AuditRecord:
    run_id: str
    timestamp_utc: str          # ISO 8601
    date_local: str             # YYYY-MM-DD (for report filename lookup)
    regime: str
    posture: str
    confidence: float
    net_score: int
    total_votes: int
    vix_level: float
    vix_change: float
    tradeable: bool
    trade_count: int
    watchlist_count: int
    rejected_count: int
    chop_count: int
    symbols_valid: int
    symbols_invalid: int
    output_paths: list[str]
    pushover_sent: bool
    pushover_error: Optional[str]
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

def new_run_id() -> str:
    return str(uuid.uuid4())


def write(record: AuditRecord, path: Path = _LOG_PATH) -> None:
    """Append one record to the audit log. Creates the file and parent dirs if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(asdict(record), sort_keys=True, default=str)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def build_record(
    *,
    run_id: str,
    started_at: datetime,
    regime_state,           # RegimeState
    trade_count: int,
    watchlist_count: int,
    rejected_count: int,
    chop_count: int,
    symbols_valid: int,
    symbols_invalid: int,
    output_paths: list[str],
    pushover_sent: bool,
    pushover_error: Optional[str],
    elapsed_seconds: float,
) -> AuditRecord:
    ts = started_at.astimezone(timezone.utc)
    return AuditRecord(
        run_id=run_id,
        timestamp_utc=ts.isoformat(),
        date_local=ts.strftime("%Y-%m-%d"),
        regime=regime_state.regime,
        posture=regime_state.posture,
        confidence=round(regime_state.confidence, 4),
        net_score=regime_state.net_score,
        total_votes=regime_state.total_votes,
        vix_level=regime_state.vix_level,
        vix_change=round(regime_state.vix_change, 6),
        tradeable=regime_state.tradeable,
        trade_count=trade_count,
        watchlist_count=watchlist_count,
        rejected_count=rejected_count,
        chop_count=chop_count,
        symbols_valid=symbols_valid,
        symbols_invalid=symbols_invalid,
        output_paths=output_paths,
        pushover_sent=pushover_sent,
        pushover_error=pushover_error,
        elapsed_seconds=round(elapsed_seconds, 2),
    )


# ---------------------------------------------------------------------------
# V1 compatibility shim — preserves import in signal_forge/pipeline.py
# ---------------------------------------------------------------------------

class AuditLogger:
    """Stub for V1 pipeline.py import compatibility. Do not use in V2."""
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path

    def write(self, *args, **kwargs):
        raise NotImplementedError("AuditLogger is a V1 stub — use signal_forge.audit.write() in V2")
