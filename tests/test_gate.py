from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from signal_forge.gate import gate_trade
from strategy_intel.models import EdgeComponent, ScoreCard


class GateTests(unittest.TestCase):
    def test_gate_fails_when_no_component_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            component = EdgeComponent(
                name="Trend Follow",
                category="momentum",
                trigger="Breakout",
                confirmation="Breadth",
                regime="trend",
                edge_source="behavioral",
                execution="shares",
                invalidation="Failed breakout",
                notes="Persistent trend continuation",
                score=ScoreCard(5, 2, 4, 5, 4, 4.3),
            )

            with patch("signal_forge.gate.storage.LIBRARY_PATH", str(library_path)):
                from strategy_intel import storage

                storage.replace_all([component])
                result = gate_trade(
                    {
                        "description": "Range scalp with no trend context",
                        "tags": ["mean reversion", "range"],
                    }
                )

            self.assertEqual(result["decision"], "FAIL")
            self.assertIsNone(result["matched_component"])
            self.assertEqual(result["score"], 0.0)

    def test_gate_fails_when_best_match_score_is_below_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            component = EdgeComponent(
                name="Open Fade",
                category="mean_reversion",
                trigger="Gap up",
                confirmation="Weak extension",
                regime="range",
                edge_source="behavioral",
                execution="shares",
                invalidation="Trend day",
                notes="Fade overstretched open",
                score=ScoreCard(3, 3, 3, 3, 3, 3.0),
            )

            with patch("signal_forge.gate.storage.LIBRARY_PATH", str(library_path)):
                from strategy_intel import storage

                storage.replace_all([component])
                result = gate_trade(
                    {
                        "description": "Open fade setup",
                        "tags": ["fade", "mean_reversion"],
                    }
                )

            self.assertEqual(result["decision"], "FAIL")
            self.assertEqual(result["matched_component"], "Open Fade")
            self.assertEqual(result["score"], 3.0)

    def test_gate_passes_and_uses_highest_scoring_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            lower = EdgeComponent(
                name="Momentum Continuation",
                category="momentum",
                trigger="Breakout",
                confirmation="Breadth",
                regime="trend",
                edge_source="behavioral",
                execution="shares",
                invalidation="Failed breakout",
                notes="Continuation move",
                score=ScoreCard(4, 2, 4, 4, 4, 4.0),
            )
            higher = EdgeComponent(
                name="Rotation Setup",
                category="mean_reversion",
                trigger="Failed push",
                confirmation="Absorption",
                regime="range",
                edge_source="structural",
                execution="shares",
                invalidation="Acceptance above highs",
                notes="Momentum exhaustion into support",
                score=ScoreCard(5, 2, 5, 5, 4, 4.45),
            )

            with patch("signal_forge.gate.storage.LIBRARY_PATH", str(library_path)):
                from strategy_intel import storage

                storage.replace_all([lower, higher])
                result = gate_trade(
                    {
                        "description": "Rotation long after exhaustion",
                        "tags": ["momentum", "support"],
                    }
                )

            self.assertEqual(result["decision"], "PASS")
            self.assertEqual(result["matched_component"], "Rotation Setup")
            self.assertEqual(result["score"], 4.45)


if __name__ == "__main__":
    unittest.main()
