from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from signal_forge.contracts import SafeguardInput
from signal_forge.rails.safeguards import SafeguardsLayer


class SafeguardsTests(unittest.TestCase):
    def test_chop_blocks_debit_expression(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            layer = SafeguardsLayer(Path(tmpdir) / "safeguards.jsonl")
            result = layer.evaluate(
                SafeguardInput(
                    market_state="CHOP",
                    volatility_regime="NORMAL",
                    expression_type="DEBIT_BULL",
                    confidence_score=85,
                    catalyst_flag=False,
                )
            )

            self.assertEqual(result.decision, "NO_TRADE")
            self.assertFalse(result.allowed)
            self.assertIn("CHOP only allows CREDIT spreads", result.reason)

    def test_low_iv_credit_mismatch_reduces_confidence_to_no_trade(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            layer = SafeguardsLayer(Path(tmpdir) / "safeguards.jsonl")
            result = layer.evaluate(
                SafeguardInput(
                    market_state="TREND",
                    volatility_regime="LOW",
                    expression_type="CREDIT_BULL",
                    confidence_score=72,
                    catalyst_flag=False,
                )
            )

            self.assertEqual(result.confidence, 57)
            self.assertEqual(result.decision, "NO_TRADE")
            self.assertIn("Adjusted confidence fell below 70", result.reason)

    def test_override_allows_blocked_setup_and_logs_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "safeguards.jsonl"
            layer = SafeguardsLayer(log_path)
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
            payload = json.loads(log_path.read_text(encoding="utf-8").strip())
            self.assertEqual(payload["safeguard_result"]["override_reason"], "EVENT_DISLOCATION")


if __name__ == "__main__":
    unittest.main()
