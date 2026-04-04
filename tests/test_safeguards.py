from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from signal_forge.backtest.trades import Trade
from signal_forge.contracts import SafeguardInput
from signal_forge.rails.safeguards import SafeguardsLayer
from signal_forge.safeguards.guardrails import validate_trade


class SafeguardsTests(unittest.TestCase):
    def test_validate_trade_rejects_chaotic_market(self) -> None:
        result = validate_trade(
            Trade("SPY", "bullish", "call_debit", 100.0, 98.0, 104.0),
            {"market_quality": "CHAOTIC", "iv_regime": "low"},
        )

        self.assertFalse(result["approved"])
        self.assertIn("Market quality is CHAOTIC, trade rejected", result["reasons"])

    def test_validate_trade_requires_high_quality_for_mixed_market(self) -> None:
        result = validate_trade(
            Trade("SPY", "bullish", "call_debit", 100.0, 99.0, 102.0),
            {"market_quality": "MIXED", "iv_regime": "low"},
        )

        self.assertFalse(result["approved"])
        self.assertIn("MIXED market only allows high-quality setups", result["reasons"])

    def test_safeguards_layer_logs_override_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            layer = SafeguardsLayer(Path(tmpdir) / "safeguards.jsonl")
            result = layer.evaluate(
                SafeguardInput(
                    market_state="MIXED",
                    volatility_regime="HIGH",
                    expression_type="CREDIT_BEAR",
                    confidence_score=40,
                    catalyst_flag=True,
                    override_flag=True,
                    override_reason="EVENT_DISLOCATION",
                )
            )

            self.assertEqual(result.decision, "OVERRIDE")
            self.assertTrue(result.allowed)
            payload = json.loads((Path(tmpdir) / "safeguards.jsonl").read_text(encoding="utf-8").strip())
            self.assertEqual(payload["safeguard_result"]["override_reason"], "EVENT_DISLOCATION")


if __name__ == "__main__":
    unittest.main()
