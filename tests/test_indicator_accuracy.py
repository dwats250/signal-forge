from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from signal_forge.validation.indicator_accuracy import validate_indicator_accuracy
from signal_forge.validation.pine_signal_adapter import assess_pine_v1_bar_data, generate_signal_forge_v1_signals


class IndicatorAccuracyTests(unittest.TestCase):
    def test_pine_signal_adapter_emits_ready_and_alert_events(self) -> None:
        bar_data = {
            "SPY": _build_spy_like_day("SPY", start_price=100.0),
            "QQQ": _build_spy_like_day("QQQ", start_price=200.0),
        }

        signals = generate_signal_forge_v1_signals(bar_data)

        self.assertEqual([signal.signal_type for signal in signals["SPY"]], ["ready", "alert_breakout"])
        self.assertEqual([signal.direction for signal in signals["SPY"]], ["bullish", "bullish"])

    def test_harness_consumes_pine_generated_events(self) -> None:
        bar_data = {
            "SPY": _build_spy_like_day("SPY", start_price=100.0),
            "QQQ": _build_spy_like_day("QQQ", start_price=200.0),
        }

        result = validate_indicator_accuracy(bar_data)

        self.assertGreaterEqual(len(result.events), 2)
        self.assertGreaterEqual(result.summary["total_signals"], 2)
        self.assertIn("ready", result.summary["by_signal_type"])
        self.assertIn("alert_breakout", result.summary["by_signal_type"])

    def test_no_signal_case_is_handled_cleanly(self) -> None:
        bar_data = {"AAPL": _build_spy_like_day("AAPL", start_price=150.0)}

        assessment = assess_pine_v1_bar_data(bar_data)
        result = validate_indicator_accuracy(bar_data)

        self.assertTrue(assessment.supported)
        self.assertEqual(result.events, [])
        self.assertEqual(result.summary["total_signals"], 0)


def _build_spy_like_day(ticker: str, *, start_price: float) -> list[dict[str, object]]:
    base_time = datetime(2026, 4, 7, 9, 30, tzinfo=timezone(timedelta(hours=-4)))
    closes = [
        start_price + 0.0,
        start_price + 0.15,
        start_price + 0.30,
        start_price + 0.35,
        start_price + 0.31,
        start_price + 0.32,
        start_price + 0.67,
        start_price + 0.98,
        start_price + 1.45,
        start_price + 1.62,
        start_price + 1.80,
        start_price + 1.98,
        start_price + 2.12,
        start_price + 2.30,
        start_price + 2.46,
        start_price + 2.63,
        start_price + 2.82,
        start_price + 3.01,
        start_price + 3.22,
        start_price + 3.45,
        start_price + 3.66,
        start_price + 3.88,
        start_price + 4.10,
        start_price + 4.31,
        start_price + 4.54,
        start_price + 4.76,
        start_price + 4.99,
        start_price + 5.24,
        start_price + 5.50,
        start_price + 5.77,
        start_price + 6.05,
        start_price + 6.34,
    ]
    volumes = [1000, 1020, 1040, 1060, 1080, 1100, 2600, 2200] + [1800] * (len(closes) - 8)

    bars: list[dict[str, object]] = []
    previous_close = closes[0] - 0.08
    for index, close in enumerate(closes):
        high = close + 0.20 if index <= 5 else close + 0.03
        low = close - 0.03
        if index == 7:
            high = close + 0.12
            low = close - 0.05
        if index == 6:
            high = close + 0.05
            low = close - 0.06
        bars.append(
            {
                "timestamp": (base_time + timedelta(minutes=5 * index)).isoformat(),
                "open": previous_close,
                "high": high,
                "low": low,
                "close": close,
                "volume": float(volumes[index]),
                "timeframe": "5M",
                "atr": 0.35,
                "regime": "bullish",
                "market_quality": "clean",
            }
        )
        previous_close = close

    return bars


if __name__ == "__main__":
    unittest.main()
