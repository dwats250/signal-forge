from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from strategy_intel import cli, storage
from strategy_intel.models import EdgeComponent, ScoreCard
from strategy_intel.scorer import score_component


class StrategyIntelTests(unittest.TestCase):
    def test_score_calculation_is_correct(self) -> None:
        component = EdgeComponent(
            name="Trend Follow",
            category="momentum",
            trigger="Breakout",
            confirmation="Breadth",
            regime="trend",
            edge_source="behavioral",
            execution="shares",
            invalidation="Failed breakout",
            notes="Persistent trend",
            score=ScoreCard(
                persistence=5,
                crowding=2,
                clarity=4,
                regime_fit=5,
                exploitability=3,
            ),
        )

        scored = score_component(component)
        self.assertEqual(scored.total_score, 4.30)

    def test_add_path_stores_component(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            responses = iter(
                [
                    "Gap Fade",
                    "mean_reversion",
                    "Large open gap",
                    "Weak follow-through",
                    "range",
                    "behavioral",
                    "shares",
                    "Gap extension",
                    "Fades best after overreaction",
                    "4",
                    "2",
                    "5",
                    "4",
                    "3",
                ]
            )

            with patch.object(storage, "LIBRARY_PATH", str(library_path)):
                with patch("builtins.input", side_effect=lambda _prompt: next(responses)):
                    with redirect_stdout(io.StringIO()):
                        cli.cmd_add(None)

                components = storage.load_components()

            self.assertEqual(len(components), 1)
            self.assertEqual(components[0].name, "Gap Fade")
            self.assertEqual(components[0].score.total_score, 4.05)

    def test_list_sorts_by_descending_total_score(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            low = EdgeComponent(
                name="Lower Score",
                category="volatility",
                trigger="Trigger",
                confirmation="Confirm",
                regime="range",
                edge_source="structural",
                execution="options",
                invalidation="Invalidation",
                notes="Low",
                score=ScoreCard(2, 4, 2, 2, 2, 2.0),
            )
            high = EdgeComponent(
                name="Higher Score",
                category="momentum",
                trigger="Trigger",
                confirmation="Confirm",
                regime="trend",
                edge_source="behavioral",
                execution="shares",
                invalidation="Invalidation",
                notes="High",
                score=ScoreCard(5, 1, 5, 5, 5, 5.0),
            )

            with patch.object(storage, "LIBRARY_PATH", str(library_path)):
                storage.replace_all([low, high])
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    cli.cmd_list(None)

            output = stdout.getvalue()
            self.assertLess(output.find("Higher Score"), output.find("Lower Score"))

    def test_query_filters_case_insensitively_and_sorts_by_score(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            name_match = EdgeComponent(
                name="Momentum Ignition",
                category="momentum",
                trigger="Trigger",
                confirmation="Confirm",
                regime="trend",
                edge_source="behavioral",
                execution="shares",
                invalidation="Invalidation",
                notes="Fast move",
                score=ScoreCard(4, 2, 4, 4, 4, 4.0),
            )
            notes_match = EdgeComponent(
                name="Rotation Setup",
                category="mean_reversion",
                trigger="Trigger",
                confirmation="Confirm",
                regime="range",
                edge_source="structural",
                execution="shares",
                invalidation="Invalidation",
                notes="Momentum exhaustion into support",
                score=ScoreCard(5, 2, 5, 5, 4, 4.45),
            )
            non_match = EdgeComponent(
                name="Income Carry",
                category="yield",
                trigger="Trigger",
                confirmation="Confirm",
                regime="trend",
                edge_source="mechanical",
                execution="shares",
                invalidation="Invalidation",
                notes="Defensive posture",
                score=ScoreCard(3, 3, 3, 3, 3, 3.0),
            )

            with patch.object(storage, "LIBRARY_PATH", str(library_path)):
                storage.replace_all([name_match, notes_match, non_match])
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    cli.cmd_query(type("Args", (), {"term": "MOMENTUM"})())

            output = stdout.getvalue()
            self.assertIn("Rotation Setup", output)
            self.assertIn("Momentum Ignition", output)
            self.assertNotIn("Income Carry", output)
            self.assertLess(output.find("Rotation Setup"), output.find("Momentum Ignition"))


if __name__ == "__main__":
    unittest.main()
