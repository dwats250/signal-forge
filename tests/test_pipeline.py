from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from signal_forge.pipeline import SignalForgePipeline


class PipelineTests(unittest.TestCase):
    def test_aligned_bearish_flow_is_deployable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = SignalForgePipeline(Path(tmpdir) / "audit.jsonl")
            result = pipeline.run(
                {
                    "macro": {"state": "bearish", "confidence": "high", "key_factors": ["macro weak"]},
                    "geo": {"state": "bearish", "confidence": "medium", "key_factors": ["risk premium rising"]},
                    "market_quality": {"state": "bearish", "confidence": "medium", "key_factors": ["breadth poor"]},
                    "options": {"state": "bearish", "confidence": "high", "key_factors": ["puts bid"]},
                }
            )

            self.assertEqual(result["thesis"]["direction"], "bearish")
            self.assertEqual(result["thesis"]["confidence"], "high")
            self.assertTrue(result["conflict"]["deployment_allowed"])
            self.assertEqual(result["conflict"]["risk_level"], "low")

    def test_structural_conflict_stays_allowed_but_constrained(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = SignalForgePipeline(Path(tmpdir) / "audit.jsonl")
            result = pipeline.run(
                {
                    "macro": {
                        "state": "bearish",
                        "confidence": "high",
                        "key_factors": ["macro trend lower"],
                        "time_horizon": "macro",
                    },
                    "geo": {"state": "neutral", "confidence": "medium", "key_factors": ["geo contained"]},
                    "market_quality": {"state": "bearish", "confidence": "medium", "key_factors": ["quality weak"]},
                    "options": {
                        "state": "bullish",
                        "confidence": "high",
                        "key_factors": ["escape window active"],
                        "time_horizon": "intraday",
                        "special_flags": {"escape_window_state": "strong"},
                    },
                }
            )

            self.assertEqual(result["thesis"]["direction"], "bearish")
            self.assertIn("structural", result["conflict"]["conflict_types"])
            self.assertIn("allow tactical trade only with defined exit plan", result["conflict"]["constraints"])
            self.assertTrue(result["conflict"]["deployment_allowed"])

    def test_geo_blocker_blocks_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = Path(tmpdir) / "audit.jsonl"
            pipeline = SignalForgePipeline(audit_path)
            result = pipeline.run(
                {
                    "macro": {"state": "bullish", "confidence": "high", "key_factors": ["macro supportive"]},
                    "geo": {
                        "state": "neutral",
                        "confidence": "high",
                        "key_factors": ["event shock pending"],
                        "special_flags": {"event_shock": True},
                    },
                    "market_quality": {"state": "bullish", "confidence": "medium", "key_factors": ["market stable"]},
                    "options": {"state": "bullish", "confidence": "medium", "key_factors": ["calls active"]},
                }
            )

            self.assertFalse(result["conflict"]["deployment_allowed"])
            self.assertEqual(result["conflict"]["risk_level"], "blocked")
            self.assertEqual(result["log_entry"]["decision"], "blocked")

            lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            self.assertEqual(payload["log_entry"]["decision"], "blocked")


if __name__ == "__main__":
    unittest.main()
