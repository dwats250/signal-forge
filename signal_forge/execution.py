from __future__ import annotations

from signal_forge.contracts import (
    AgentOutput,
    ConflictResult,
    ExecutionInput,
    SafeguardResult,
    Thesis,
)


CONFIDENCE_SCORES = {"low": 45, "medium": 65, "high": 85}


class ExecutionInterface:
    def build_input(
        self,
        thesis: Thesis,
        conflict: ConflictResult,
        safeguard: SafeguardResult | None = None,
        market_state: str | None = None,
        volatility_regime: str | None = None,
        expression_type: str | None = None,
        confidence_score: int | None = None,
        catalyst_flag: bool = False,
    ) -> ExecutionInput:
        return ExecutionInput(
            thesis=thesis,
            conflict=conflict,
            market_state=market_state,
            volatility_regime=volatility_regime,
            expression_type=expression_type,
            confidence_score=confidence_score,
            catalyst_flag=catalyst_flag,
            safeguard=safeguard,
        )

    def decision_label(self, execution_input: ExecutionInput) -> str:
        if execution_input.safeguard is not None:
            if execution_input.safeguard.decision == "NO_TRADE":
                return "no_trade"
            if execution_input.safeguard.decision == "OVERRIDE":
                return "override"
        if not execution_input.conflict.deployment_allowed:
            return "blocked"
        if execution_input.conflict.risk_level == "high":
            return "selective"
        return "deployable"

    def detect_market_state(self, thesis: Thesis, conflict: ConflictResult) -> str:
        if thesis.direction in {"mixed", "neutral", "blocked"}:
            return "MIXED"
        if conflict.risk_level == "high" or "directional" in conflict.conflict_types:
            return "CHOP"
        options_output = thesis.agent_outputs.get("options")
        if options_output and options_output.special_flags.get("iv_state") == "expanding":
            return "EXPANSION"
        return "TREND"

    def detect_volatility_regime(self, outputs: dict[str, AgentOutput]) -> str:
        options_output = outputs.get("options")
        if options_output is None:
            return "NORMAL"
        iv_state = options_output.special_flags.get("iv_state")
        if iv_state == "expanding":
            return "HIGH"
        if iv_state == "compressed":
            return "LOW"
        return "NORMAL"

    def select_expression(self, thesis: Thesis, volatility_regime: str) -> str:
        bullish = thesis.direction == "bullish"
        if volatility_regime == "HIGH":
            return "CREDIT_BULL" if bullish else "CREDIT_BEAR"
        if volatility_regime == "LOW":
            return "DEBIT_BULL" if bullish else "DEBIT_BEAR"
        return "CREDIT_BULL" if bullish else "CREDIT_BEAR"

    def confidence_score(self, thesis: Thesis, conflict: ConflictResult) -> int:
        score = CONFIDENCE_SCORES[thesis.confidence]
        if conflict.risk_level == "medium":
            score -= 10
        elif conflict.risk_level == "high":
            score -= 20
        return max(0, min(100, score))

    def catalyst_flag(self, outputs: dict[str, AgentOutput]) -> bool:
        geo_output = outputs.get("geo")
        if geo_output and geo_output.special_flags.get("event_shock") is True:
            return True
        options_output = outputs.get("options")
        return bool(options_output and options_output.special_flags.get("catalyst_flag") is True)
