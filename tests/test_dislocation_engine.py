from __future__ import annotations

import unittest

from signal_forge.contracts import DislocationReading
from signal_forge.dislocation_engine import classify_dislocation


class DislocationEngineTests(unittest.TestCase):
    def test_classifies_aligned_move_as_clean(self) -> None:
        reading = DislocationReading(
            futures_symbol="ES",
            etf_symbol="SPY",
            futures_pct_change=0.8,
            etf_pct_change=0.1,
        )

        result = classify_dislocation(reading)

        self.assertEqual(result.signal, "CLEAN")
        self.assertAlmostEqual(result.divergence, 0.7)
        self.assertEqual(result.pair, "ES/SPY")
        self.assertEqual(result.futures_symbol, "ES")
        self.assertEqual(result.etf_symbol, "SPY")
        self.assertEqual(result.direction_relation, "same_direction")
        self.assertEqual(result.leader, "futures")
        self.assertEqual(result.divergence_band, "low")
        self.assertEqual(result.explanation, "Same direction, futures leading, low divergence.")
        self.assertEqual(result.to_dict()["divergence"], 0.7)

    def test_classifies_moderate_divergence_as_mixed(self) -> None:
        reading = DislocationReading(
            futures_symbol="NQ",
            etf_symbol="QQQ",
            futures_pct_change=2.6,
            etf_pct_change=0.4,
        )

        result = classify_dislocation(reading)

        self.assertEqual(result.signal, "MIXED")
        self.assertAlmostEqual(result.divergence, 2.2)
        self.assertEqual(result.pair, "NQ/QQQ")
        self.assertEqual(result.direction_relation, "same_direction")
        self.assertEqual(result.leader, "futures")
        self.assertEqual(result.divergence_band, "moderate")
        self.assertEqual(
            result.explanation,
            "Same direction, futures leading, moderate divergence.",
        )
        self.assertEqual(result.to_dict()["divergence"], 2.2)

    def test_classifies_opposite_direction_as_dislocation(self) -> None:
        reading = DislocationReading(
            futures_symbol="CL",
            etf_symbol="XLE",
            futures_pct_change=2.5,
            etf_pct_change=-0.4,
        )

        result = classify_dislocation(reading)

        self.assertEqual(result.signal, "DISLOCATION")
        self.assertAlmostEqual(result.divergence, 2.9)
        self.assertEqual(result.pair, "CL/XLE")
        self.assertEqual(result.direction_relation, "opposite_direction")
        self.assertEqual(result.leader, "futures")
        self.assertEqual(result.divergence_band, "moderate")
        self.assertEqual(
            result.explanation,
            "Opposite direction, futures leading, moderate divergence.",
        )
        self.assertEqual(result.to_dict()["divergence"], 2.9)


if __name__ == "__main__":
    unittest.main()
