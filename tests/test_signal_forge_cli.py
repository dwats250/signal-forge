from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from signal_forge import __main__


class SignalForgeCliTests(unittest.TestCase):
    def test_gate_subcommand_prints_gate_result(self) -> None:
        stdout = io.StringIO()
        with patch("signal_forge.__main__.gate_trade", return_value={"decision": "PASS"}):
            with patch(
                "sys.argv",
                ["signal_forge", "gate", "--description", "Trend trade", "--tag", "momentum"],
            ):
                with redirect_stdout(stdout):
                    __main__.main()

        self.assertEqual(json.loads(stdout.getvalue()), {"decision": "PASS"})

    def test_backtest_demo_prints_backtest_result(self) -> None:
        stdout = io.StringIO()
        with patch(
            "signal_forge.__main__.run_backtest",
            return_value={"metrics": {"win_rate": 0.5}, "trades": []},
        ):
            with patch(
                "signal_forge.__main__.load_price_series",
                return_value=[100.0, 101.0, 102.0],
            ):
                with patch(
                    "sys.argv",
                    ["signal_forge", "backtest-demo"],
                ):
                    with redirect_stdout(stdout):
                        __main__.main()

        self.assertEqual(
            json.loads(stdout.getvalue()),
            {"metrics": {"win_rate": 0.5}, "trades": []},
        )

    def test_submit_trade_subcommand_prints_trade_record(self) -> None:
        payload = {
            "candidate": {
                "symbol": "SPY",
                "strategy_type": "equity",
                "direction": "bullish",
                "entry_trigger": {"trigger_type": "breakout", "price": 100.0},
                "stop_level": 98.0,
                "target_level": 106.0,
            },
            "market_regime": {"approved": True, "reason": "aligned"},
            "setup_result": {"valid": True, "direction": "bullish"},
            "account_size": 10000,
            "risk_percent": 0.01,
        }
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            payload_path = Path(tmpdir) / "trade.json"
            payload_path.write_text(json.dumps(payload), encoding="utf-8")
            with patch(
                "sys.argv",
                [
                    "signal_forge",
                    "submit-trade",
                    "--file",
                    str(payload_path),
                    "--log-dir",
                    tmpdir,
                ],
            ):
                with redirect_stdout(stdout):
                    __main__.main()

        result = json.loads(stdout.getvalue())
        self.assertEqual(result["state"], "READY")
        self.assertEqual(result["candidate"]["symbol"], "SPY")


if __name__ == "__main__":
    unittest.main()
