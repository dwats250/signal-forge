from __future__ import annotations

from itertools import combinations

from signal_forge.contracts import AgentOutput, ConflictResult, Thesis


CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


class ConflictRulesEngine:
    def evaluate(self, thesis: Thesis) -> ConflictResult:
        outputs = thesis.agent_outputs
        conflicts = self._detect_conflicts(outputs)
        blocked_by = self._detect_blockers(outputs)
        constraints = self._build_constraints(thesis, conflicts, blocked_by)

        deployment_allowed = not blocked_by
        risk_level = self._risk_level(thesis, conflicts, blocked_by)
        notes = self._build_notes(thesis, conflicts, blocked_by)
        dominant_domain = self._dominant_domain(outputs)
        suppressed_domains = sorted(blocked_by) if blocked_by else self._suppressed_domains(outputs, thesis.direction)

        return ConflictResult(
            deployment_allowed=deployment_allowed,
            risk_level=risk_level,
            constraints=constraints,
            notes=notes,
            conflict_types=sorted(conflicts),
            dominant_domain=dominant_domain,
            suppressed_domains=suppressed_domains,
        )

    def _detect_conflicts(self, outputs: dict[str, AgentOutput]) -> set[str]:
        conflicts: set[str] = set()
        for left, right in combinations(outputs.values(), 2):
            if left.state != right.state and "blocked" not in {left.state, right.state}:
                conflicts.add("directional")
            if abs(CONFIDENCE_ORDER[left.confidence] - CONFIDENCE_ORDER[right.confidence]) >= 2:
                conflicts.add("conviction")
            if left.time_horizon != right.time_horizon:
                conflicts.add("temporal")
            if self._structural_conflict(left, right):
                conflicts.add("structural")
            if self._volatility_conflict(left, right):
                conflicts.add("volatility")
        return conflicts

    def _structural_conflict(self, left: AgentOutput, right: AgentOutput) -> bool:
        states_differ = left.state in {"bullish", "bearish"} and right.state in {"bullish", "bearish"} and left.state != right.state
        escape_window = left.special_flags.get("escape_window_state") == "strong" or right.special_flags.get("escape_window_state") == "strong"
        return states_differ and escape_window

    def _volatility_conflict(self, left: AgentOutput, right: AgentOutput) -> bool:
        iv_expanding = left.special_flags.get("iv_state") == "expanding" or right.special_flags.get("iv_state") == "expanding"
        shock_risk = left.special_flags.get("event_shock") is True or right.special_flags.get("event_shock") is True
        return iv_expanding and shock_risk

    def _detect_blockers(self, outputs: dict[str, AgentOutput]) -> set[str]:
        blocked_by = {domain for domain, output in outputs.items() if output.state == "blocked"}
        geo_output = outputs.get("geo")
        if geo_output and geo_output.confidence == "high" and geo_output.special_flags.get("event_shock") is True:
            blocked_by.add("geo")
        return blocked_by

    def _build_constraints(self, thesis: Thesis, conflicts: set[str], blocked_by: set[str]) -> list[str]:
        if blocked_by:
            return [f"execution blocked by {domain}" for domain in sorted(blocked_by)]

        constraints: list[str] = []
        if thesis.direction == "mixed":
            constraints.append("reduce conviction and wait for alignment")
        if "directional" in conflicts:
            constraints.append("reduce sizing due to directional disagreement")
        if "temporal" in conflicts:
            constraints.append("restrict deployment to matching time horizon")
        if "structural" in conflicts:
            constraints.append("allow tactical trade only with defined exit plan")
        if "volatility" in conflicts:
            constraints.append("favor defined-risk structures during volatility conflict")
        if not constraints:
            constraints.append("no additional execution constraints")
        return constraints

    def _risk_level(self, thesis: Thesis, conflicts: set[str], blocked_by: set[str]) -> str:
        if blocked_by:
            return "blocked"
        if thesis.direction in {"mixed", "neutral"}:
            return "high"
        if {"structural", "volatility"} & conflicts:
            return "high"
        if conflicts:
            return "medium"
        return "low"

    def _build_notes(self, thesis: Thesis, conflicts: set[str], blocked_by: set[str]) -> str:
        if blocked_by:
            return f"Deployment blocked by: {', '.join(sorted(blocked_by))}."
        if not conflicts:
            return f"Thesis is {thesis.direction} with no active domain conflicts."
        ordered = ", ".join(sorted(conflicts))
        return f"Thesis is {thesis.direction} with active conflicts: {ordered}."

    def _dominant_domain(self, outputs: dict[str, AgentOutput]) -> str | None:
        ranked = sorted(
            outputs.items(),
            key=lambda item: (CONFIDENCE_ORDER[item[1].confidence], item[0]),
            reverse=True,
        )
        return ranked[0][0] if ranked else None

    def _suppressed_domains(self, outputs: dict[str, AgentOutput], direction: str) -> list[str]:
        if direction not in {"bullish", "bearish"}:
            return []
        return sorted(
            domain
            for domain, output in outputs.items()
            if output.state not in {direction, "neutral"}
        )
