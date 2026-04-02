from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from signal_forge.contracts import AgentOutput


@dataclass(slots=True)
class StubAgent:
    domain: str
    default_state: str
    default_confidence: str
    default_factors: list[str]

    def run(self, context: dict[str, Any] | None = None) -> AgentOutput:
        context = context or {}
        override = context.get(self.domain, {})
        return AgentOutput(
            domain=self.domain,
            state=override.get("state", self.default_state),
            confidence=override.get("confidence", self.default_confidence),
            key_factors=override.get("key_factors", list(self.default_factors)),
            time_horizon=override.get("time_horizon", "swing"),
            special_flags=override.get("special_flags", {}),
        )


class MacroAgent(StubAgent):
    def __init__(self) -> None:
        super().__init__(
            domain="macro",
            default_state="neutral",
            default_confidence="medium",
            default_factors=["macro backdrop unresolved"],
        )


class GeoAgent(StubAgent):
    def __init__(self) -> None:
        super().__init__(
            domain="geo",
            default_state="neutral",
            default_confidence="medium",
            default_factors=["geopolitical premium contained"],
        )


class MarketQualityAgent(StubAgent):
    def __init__(self) -> None:
        super().__init__(
            domain="market_quality",
            default_state="neutral",
            default_confidence="medium",
            default_factors=["tradability mixed"],
        )


class OptionsBehaviorAgent(StubAgent):
    def __init__(self) -> None:
        super().__init__(
            domain="options",
            default_state="neutral",
            default_confidence="medium",
            default_factors=["options surface balanced"],
        )


@dataclass(slots=True)
class DislocationFetcher:
    default_moves: dict[tuple[str, str], tuple[float, float]] = field(
        default_factory=lambda: {
            ("CL", "XLE"): (4.2, 0.1),
            ("ES", "SPY"): (0.6, 0.5),
        }
    )

    def fetch(
        self,
        futures_symbol: str,
        etf_symbol: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, float]:
        context = context or {}
        pair = (futures_symbol, etf_symbol)
        override = context.get("dislocation", {}).get(pair)
        futures_pct_change, etf_pct_change = override or self.default_moves.get(
            pair,
            (0.0, 0.0),
        )
        return {
            "futures_pct_change": futures_pct_change,
            "etf_pct_change": etf_pct_change,
        }
