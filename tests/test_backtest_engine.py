from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from signal_forge.backtest import Trade, run_backtest
from signal_forge.backtest.engine import SimpleBacktestEngine
from signal_forge.backtest.metrics import calculate_metrics
from signal_forge.data.loader import load_price_series


class BacktestEngineTests(unittest.TestCase):
    def test_run_backtest_records_win_and_timeout(self) -> None:
        trades = [
            Trade("SPY", "bullish", "call_debit", 100.0, 98.0, 104.0),
            Trade("QQQ", "bearish", "call_credit", 100.0, 102.0, 96.0),
        ]
        price_data = {
            "SPY": [100.0, 101.0, 104.5],
            "QQQ": [100.0, 99.5, 99.2, 99.0, 98.8],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_backtest(
                trades,
                price_data,
                log_path=Path(tmpdir) / "backtest_log.jsonl",
            )

            self.assertEqual(result["trades"][0]["outcome"], "win")
            self.assertEqual(result["trades"][1]["outcome"], "timeout")
            self.assertEqual(result["metrics"]["win_rate"], 0.5)
            payload = json.loads((Path(tmpdir) / "backtest_log.jsonl").read_text(encoding="utf-8").strip())
            self.assertEqual(payload["trades_tested"], 2)

    def test_metrics_capture_drawdown_and_total_return(self) -> None:
        metrics = calculate_metrics(
            [
                {"outcome": "win", "pnl": 2.0, "r_multiple": 2.0},
                {"outcome": "loss", "pnl": -1.0, "r_multiple": -1.0},
                {"outcome": "timeout", "pnl": 0.5, "r_multiple": 0.5},
            ]
        )

        self.assertEqual(metrics["win_rate"], 0.3333)
        self.assertEqual(metrics["max_drawdown"], 1.0)
        self.assertEqual(metrics["total_return"], 1.5)

    def test_loader_returns_mock_series_without_api_key(self) -> None:
        series = load_price_series("SPY")
        self.assertGreaterEqual(len(series), 2)

    def test_legacy_simple_engine_still_returns_contract_result(self) -> None:
        result = SimpleBacktestEngine().run(
            prices=[100.0, 101.0, 102.0],
            expression_type="CREDIT_BULL",
            allowed=True,
            confidence_score=90,
        )

        self.assertEqual(result.trades[0].outcome, "WIN")
        self.assertEqual(result.summary.trades, 1)


if __name__ == "__main__":
    unittest.main()
