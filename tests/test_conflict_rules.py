from __future__ import annotations

import unittest

from signal_forge.conflict_rules import ConflictRulesEngine
from signal_forge.contracts import AgentOutput, Thesis


class ConflictRulesTests(unittest.TestCase):
    def test_temporal_and_volatility_conflicts_are_detected(self) -> None:
        thesis = Thesis.create(
            direction="bullish",
            confidence="medium",
            drivers=["test"],
            invalidators=[],
            agent_outputs={
                "macro": AgentOutput("macro", "bullish", "high", ["macro"], time_horizon="macro"),
                "geo": AgentOutput("geo", "bullish", "high", ["geo"], special_flags={"event_shock": True}),
                "market_quality": AgentOutput("market_quality", "bullish", "medium", ["mq"]),
                "options": AgentOutput(
                    "options",
                    "bullish",
                    "high",
                    ["options"],
                    time_horizon="intraday",
                    special_flags={"iv_state": "expanding"},
                ),
            },
        )

        result = ConflictRulesEngine().evaluate(thesis)
        self.assertIn("temporal", result.conflict_types)
        self.assertIn("volatility", result.conflict_types)
        self.assertFalse(result.deployment_allowed)


if __name__ == "__main__":
    unittest.main()
