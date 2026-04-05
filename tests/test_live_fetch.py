from __future__ import annotations

import unittest

from signal_forge.data.live_fetch import (
    LiveDataUnavailableError,
    build_live_context,
    fetch_market_snapshot,
)


class FakeProvider:
    def __init__(self, name: str, histories: dict[str, list[float]] | None = None, reason: str | None = None):
        self._name = name
        self.histories = histories or {}
        self.reason = reason

    @property
    def name(self) -> str:
        return self._name

    def fetch_histories(self, symbol_map: dict[str, str]) -> tuple[dict[str, list[float]], str | None]:
        filtered = {ticker: self.histories[ticker] for ticker in symbol_map if ticker in self.histories}
        return filtered, self.reason


class LiveFetchTests(unittest.TestCase):
    def test_fetch_market_snapshot_uses_fallback_for_missing_symbols(self) -> None:
        snapshot = fetch_market_snapshot(
            providers=[
                FakeProvider(
                    "fmp",
                    histories={
                        "SPY": [100, 101, 102, 103, 104, 105],
                        "QQQ": [200, 201, 202, 203, 204, 205],
                    },
                ),
                FakeProvider(
                    "stooq",
                    histories={
                        "IWM": [50, 50.5, 51, 51.5, 52, 52.5],
                        "DXY": [30, 30.1, 30.2, 30.3, 30.4, 30.5],
                        "VIX": [20, 19.5, 19, 18.5, 18, 17.5],
                        "US10Y": [90, 90.1, 90.2, 90.3, 90.4, 90.5],
                        "GOLD": [180, 181, 182, 183, 184, 185],
                        "OIL": [70, 71, 72, 73, 74, 75],
                        "XLE": [80, 80.5, 81, 81.5, 82, 82.5],
                    },
                ),
            ]
        )

        self.assertEqual(snapshot["SPY"]["source"], "fmp")
        self.assertEqual(snapshot["IWM"]["source"], "stooq")
        self.assertEqual(snapshot["_meta"]["missing_tickers"], [])

    def test_build_live_context_handles_missing_data(self) -> None:
        snapshot = {
            "SPY": {"day_chg": 1.2},
            "QQQ": {"day_chg": 0.8},
            "IWM": {"day_chg": None},
            "DXY": {"day_chg": -0.2},
            "VIX": {"day_chg": -1.0},
            "US10Y": {"day_chg": None},
            "GOLD": {"day_chg": 0.3},
            "OIL": {"day_chg": 0.4},
            "XLE": {"day_chg": 0.9},
            "_meta": {"fetched_at": "2026-04-05T00:00:00+00:00", "sources": ["fmp"], "missing_tickers": ["US10Y"]},
        }

        context = build_live_context(snapshot)

        self.assertIn("macro", context)
        self.assertIn("market_quality", context)
        self.assertEqual(context["dislocation"][("CL", "XLE")], (0.4, 0.9))

    def test_fetch_market_snapshot_raises_when_any_required_ticker_missing(self) -> None:
        with self.assertRaises(LiveDataUnavailableError):
            fetch_market_snapshot(
                providers=[
                    FakeProvider(
                        "fmp",
                        histories={
                            "SPY": [100, 101, 102, 103, 104, 105],
                            "QQQ": [200, 201, 202, 203, 204, 205],
                        },
                    ),
                    FakeProvider("stooq", histories={}),
                ]
            )

    def test_fetch_market_snapshot_raises_when_all_providers_fail(self) -> None:
        with self.assertRaises(LiveDataUnavailableError):
            fetch_market_snapshot(
                providers=[
                    FakeProvider("fmp", histories={}, reason="fmp down"),
                    FakeProvider("stooq", histories={}, reason="stooq down"),
                ]
            )


if __name__ == "__main__":
    unittest.main()
