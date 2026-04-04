from __future__ import annotations

import json
from pathlib import Path

from signal_forge.backtest.trades import Trade
from signal_forge.contracts import SafeguardInput, SafeguardResult
from signal_forge.safeguards.guardrails import validate_trade


class SafeguardsLayer:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def evaluate(self, guard_input: SafeguardInput) -> SafeguardResult:
        trade = Trade(
            symbol="UNKNOWN",
            direction="bullish" if guard_input.expression_type.endswith("BULL") else "bearish",
            structure=self._structure_from_expression(guard_input.expression_type),
            entry_price=100.0,
            stop=99.0 if guard_input.expression_type.endswith("BULL") else 101.0,
            target=102.5 if guard_input.expression_type.endswith("BULL") else 97.5,
            timeout_bars=5,
        )
        evaluation = validate_trade(
            trade,
            {
                "market_quality": self._market_quality(guard_input.market_state),
                "iv_regime": guard_input.volatility_regime.lower(),
            },
        )

        decision = "TRADE" if evaluation["approved"] else "NO_TRADE"
        allowed = evaluation["approved"]
        reasons = list(evaluation["reasons"])

        if guard_input.confidence_score < 70:
            decision = "NO_TRADE"
            allowed = False
            reasons.append("Confidence score below 70")
        if guard_input.catalyst_flag and trade.structure.endswith("credit"):
            decision = "NO_TRADE"
            allowed = False
            reasons.append("Catalyst risk blocks credit spreads")
        if guard_input.override_flag:
            decision = "OVERRIDE"
            allowed = True
            reasons.append(f"Manual override applied: {guard_input.override_reason}")

        result = SafeguardResult(
            decision=decision,
            allowed=allowed,
            reason="; ".join(reasons),
            confidence=max(int(evaluation["score"] * 100), 0),
            blocked_expressions=[],
            posture=self._posture(self._market_quality(guard_input.market_state), trade.structure),
            override_flag=guard_input.override_flag,
            override_reason=guard_input.override_reason,
        )
        self.log(guard_input, result)
        return result

    def log(self, guard_input: SafeguardInput, result: SafeguardResult) -> None:
        payload = {
            "safeguard_input": guard_input.to_dict(),
            "safeguard_result": result.to_dict(),
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True))
            handle.write("\n")

    def _market_quality(self, market_state: str) -> str:
        if market_state in {"CHOP", "MIXED"}:
            return "MIXED"
        if market_state == "CHAOS":
            return "CHAOTIC"
        return "CLEAN"

    def _structure_from_expression(self, expression_type: str) -> str:
        mapping = {
            "DEBIT_BULL": "call_debit",
            "DEBIT_BEAR": "put_debit",
            "CREDIT_BULL": "put_credit",
            "CREDIT_BEAR": "call_credit",
        }
        return mapping[expression_type]

    def _posture(self, market_quality: str, structure: str) -> str:
        if market_quality == "MIXED":
            return "WAIT"
        if market_quality == "CHAOTIC":
            return "NO TRADE"
        if structure.endswith("credit"):
            return "SELL PREMIUM"
        return "BUY CONVEXITY"
