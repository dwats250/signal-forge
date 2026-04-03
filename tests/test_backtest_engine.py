from __future__ import annotations

import unittest

from signal_forge.backtest.engine import SimpleBacktestEngine


class SimpleBacktestEngineTests(unittest.TestCase):
    def test_credit_bull_wins_when_price_holds_support(self) -> None:
        result = SimpleBacktestEngine().run(
            prices=[100.0, 100.4, 100.2, 100.1, 100.5, 100.3],
            expression_type="CREDIT_BULL",
            allowed=True,
            confidence_score=85,
        )

        self.assertEqual(result.trades[0].outcome, "WIN")
        self.assertEqual(result.summary.win_rate, 1.0)
        self.assertEqual(result.summary.no_trade_count, 0)

    def test_debit_bear_loses_when_target_is_missed(self) -> None:
        result = SimpleBacktestEngine().run(
            prices=[100.0, 99.8, 99.5, 99.6, 99.4, 99.2],
            expression_type="DEBIT_BEAR",
            allowed=True,
            confidence_score=85,
        )

        self.assertEqual(result.trades[0].outcome, "LOSS")
        self.assertLess(result.summary.expectancy, 0)

    def test_blocked_setup_is_counted_as_no_trade(self) -> None:
        result = SimpleBacktestEngine().run(
            prices=[100.0, 101.0, 102.0],
            expression_type="DEBIT_BULL",
            allowed=False,
            confidence_score=90,
        )

        self.assertTrue(result.trades[0].no_trade)
        self.assertEqual(result.summary.no_trade_count, 1)
        self.assertEqual(result.summary.trades, 0)


if __name__ == "__main__":
    unittest.main()
