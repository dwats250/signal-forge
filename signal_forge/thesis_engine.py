from __future__ import annotations

from collections import Counter

from signal_forge.contracts import AgentOutput, Thesis


CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


class ThesisEngine:
    def build(self, agent_outputs: dict[str, AgentOutput]) -> Thesis:
        if not agent_outputs:
            raise ValueError("agent_outputs must not be empty")

        direction = self._resolve_direction(agent_outputs)
        confidence = self._resolve_confidence(agent_outputs, direction)
        drivers = self._collect_drivers(agent_outputs)
        invalidators = self._collect_invalidators(agent_outputs, direction)
        return Thesis.create(
            direction=direction,
            confidence=confidence,
            drivers=drivers,
            invalidators=invalidators,
            agent_outputs=agent_outputs,
        )

    def _resolve_direction(self, agent_outputs: dict[str, AgentOutput]) -> str:
        states = [output.state for output in agent_outputs.values() if output.state != "neutral"]
        if not states:
            return "neutral"

        counts = Counter(states)
        if "blocked" in counts:
            return "blocked"
        if len(counts) == 1:
            return states[0]
        if counts.get("bullish", 0) == counts.get("bearish", 0):
            return "mixed"
        return "bullish" if counts.get("bullish", 0) > counts.get("bearish", 0) else "bearish"

    def _resolve_confidence(self, agent_outputs: dict[str, AgentOutput], direction: str) -> str:
        confidences = [CONFIDENCE_ORDER[output.confidence] for output in agent_outputs.values()]
        low_coverage = min(confidences)
        aligned = sum(1 for output in agent_outputs.values() if output.state == direction)

        if direction in {"blocked", "mixed", "neutral"}:
            return "low"
        if low_coverage >= CONFIDENCE_ORDER["medium"] and aligned >= 3:
            return "high"
        if aligned >= 2:
            return "medium"
        return "low"

    def _collect_drivers(self, agent_outputs: dict[str, AgentOutput]) -> list[str]:
        seen: set[str] = set()
        drivers: list[str] = []
        for output in agent_outputs.values():
            for factor in output.key_factors:
                if factor not in seen:
                    seen.add(factor)
                    drivers.append(factor)
        return drivers

    def _collect_invalidators(self, agent_outputs: dict[str, AgentOutput], direction: str) -> list[str]:
        invalidators: list[str] = []
        for domain, output in agent_outputs.items():
            if output.state == "blocked":
                invalidators.append(f"{domain} blocked deployment")
            elif direction in {"bullish", "bearish"} and output.state not in {direction, "neutral"}:
                invalidators.append(f"{domain} opposes the thesis")
            if output.confidence == "low":
                invalidators.append(f"{domain} confidence degraded")
        return invalidators
