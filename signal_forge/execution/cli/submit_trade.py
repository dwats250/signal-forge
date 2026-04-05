from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from signal_forge.execution.models import (
    EntryTrigger,
    OptionStructure,
    StrategyType,
    TradeCandidate,
    TradeDirection,
)
from signal_forge.execution.models.core import utc_now
from signal_forge.execution.orchestrator import ExecutionOrchestrator


def load_json_payload(path: str | None) -> dict[str, Any]:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    if not sys.stdin.isatty():
        return json.load(sys.stdin)
    raise SystemExit("execution command requires --file or JSON on stdin")


def candidate_from_payload(payload: dict[str, Any]) -> TradeCandidate:
    option_payload = payload.get("option_structure")
    option_structure = OptionStructure(**option_payload) if option_payload else None
    return TradeCandidate(
        symbol=payload["symbol"],
        strategy_type=StrategyType(payload["strategy_type"]),
        direction=TradeDirection(payload["direction"]),
        entry_trigger=EntryTrigger(**payload["entry_trigger"]),
        stop_level=payload["stop_level"],
        target_level=payload["target_level"],
        option_structure=option_structure,
        score=payload.get("score", 1.0),
        ema_aligned=payload.get("ema_aligned", True),
        atr=payload.get("atr"),
        averaging_down=payload.get("averaging_down", False),
        trade_id=payload.get("trade_id") or str(uuid4()),
        created_at=payload.get("created_at") or utc_now(),
    )


def submit_trade_from_payload(
    payload: dict[str, Any],
    *,
    log_dir: Path,
) -> dict[str, Any]:
    orchestrator = ExecutionOrchestrator(log_dir)
    candidate = candidate_from_payload(payload["candidate"])
    record = orchestrator.submit_trade(
        candidate,
        market_regime=payload.get("market_regime"),
        setup_result=payload.get("setup_result"),
        account_size=payload["account_size"],
        risk_percent=payload["risk_percent"],
    )
    return record.to_dict()
