from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
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
                "sys.argv",
                ["signal_forge", "backtest-demo"],
            ):
                with redirect_stdout(stdout):
                    __main__.main()

        self.assertEqual(
            json.loads(stdout.getvalue()),
            {"metrics": {"win_rate": 0.5}, "trades": []},
        )


if __name__ == "__main__":
    unittest.main()
