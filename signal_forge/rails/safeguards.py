from __future__ import annotations

import json
from pathlib import Path

from signal_forge.contracts import SafeguardInput, SafeguardResult


class SafeguardsLayer:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def evaluate(self, guard_input: SafeguardInput) -> SafeguardResult:
        confidence = guard_input.confidence_score
        reasons: list[str] = []
        blocked_expressions: list[str] = []

        decision = "TRADE"
        allowed = True
        posture = self._posture(guard_input.market_state, guard_input.expression_type)

        if guard_input.market_state == "CHOP":
            blocked_expressions = ["DEBIT_BULL", "DEBIT_BEAR"]
            if guard_input.expression_type.startswith("DEBIT"):
                decision = "NO_TRADE"
                allowed = False
                reasons.append("CHOP only allows CREDIT spreads")
        elif guard_input.market_state == "EXPANSION":
            blocked_expressions = ["CREDIT_BULL", "CREDIT_BEAR"]
            if guard_input.expression_type.startswith("CREDIT"):
                decision = "NO_TRADE"
                allowed = False
                reasons.append("EXPANSION only allows DEBIT spreads")
        elif guard_input.market_state == "MIXED":
            blocked_expressions = [
                "CREDIT_BULL",
                "CREDIT_BEAR",
                "DEBIT_BULL",
                "DEBIT_BEAR",
            ]
            decision = "NO_TRADE"
            allowed = False
            reasons.append("MIXED market state defaults to NO_TRADE")

        mismatch_penalty = self._volatility_penalty(guard_input)
        if mismatch_penalty:
            confidence = max(0, confidence - mismatch_penalty)
            reasons.append(f"Volatility mismatch reduced confidence by {mismatch_penalty}")

        if guard_input.confidence_score < 70:
            decision = "NO_TRADE"
            allowed = False
            reasons.append("Confidence score below 70")
        elif confidence < 70:
            decision = "NO_TRADE"
            allowed = False
            reasons.append("Adjusted confidence fell below 70")

        if guard_input.catalyst_flag and guard_input.expression_type.startswith("CREDIT"):
            decision = "NO_TRADE"
            allowed = False
            reasons.append("Catalyst risk blocks CREDIT spreads")

        if guard_input.override_flag:
            decision = "OVERRIDE"
            allowed = True
            reasons.append(f"Manual override applied: {guard_input.override_reason}")

        if not reasons:
            reasons.append("Expression passed safeguard checks")

        result = SafeguardResult(
            decision=decision,
            allowed=allowed,
            reason="; ".join(reasons),
            confidence=confidence,
            blocked_expressions=blocked_expressions,
            posture=posture,
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

    def _volatility_penalty(self, guard_input: SafeguardInput) -> int:
        if guard_input.volatility_regime == "HIGH" and guard_input.expression_type.startswith("DEBIT"):
            return 15
        if guard_input.volatility_regime == "LOW" and guard_input.expression_type.startswith("CREDIT"):
            return 15
        return 0

    def _posture(self, market_state: str, expression_type: str) -> str:
        if market_state == "CHOP":
            return "SELL PREMIUM / WAIT"
        if market_state == "EXPANSION":
            return "BUY CONVEXITY / WAIT"
        if market_state == "MIXED":
            return "WAIT"
        if expression_type.startswith("CREDIT"):
            return "SELL PREMIUM"
        return "BUY CONVEXITY"
