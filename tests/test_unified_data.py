from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from signal_forge.data.unified_data import UnifiedMarketDataClient


class FakeProvider:
    def __init__(self, name: str, histories: dict[str, list[float]] | None = None, reason: str | None = None):
        self._name = name
        self.histories = histories or {}
        self.reason = reason

    @property
    def name(self) -> str:
        return self._name

    def fetch_histories(self, symbol_map: dict[str, str]) -> tuple[dict[str, list[float]], object]:
        filtered = {ticker: self.histories[ticker] for ticker in symbol_map if ticker in self.histories}
        return filtered, self.reason


class UnifiedDataTests(unittest.TestCase):
    def test_fetch_entries_uses_first_provider_with_usable_data(self) -> None:
        client = UnifiedMarketDataClient(
            providers=[
                FakeProvider("fmp", {}),
                FakeProvider("stooq", {"SPY": [100.0, 101.0, 102.0]}),
                FakeProvider("yfinance", {"SPY": [90.0, 95.0, 96.0]}),
            ],
            provider_symbols={
                "fmp": {"SPY": "SPY"},
                "stooq": {"SPY": "spy.us"},
                "yfinance": {"SPY": "SPY"},
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            outcome = client.fetch_entries(
                ["SPY"],
                cache_path=Path(tmpdir) / "market.json",
                fallback_builder=lambda: {"SPY": {"formatted": "stub"}},
                formatter=lambda value, ticker: f"${value:.2f}",
                yield_tickers=set(),
            )

        self.assertEqual(outcome.source, "stooq")
        self.assertFalse(outcome.fallback_used)
        self.assertEqual(outcome.data["SPY"]["formatted"], "$102.00")

    def test_fetch_entries_falls_back_to_cache_before_stub(self) -> None:
        client = UnifiedMarketDataClient(
            providers=[FakeProvider("fmp", {}), FakeProvider("stooq", {}), FakeProvider("yfinance", {})],
            provider_symbols={"fmp": {"SPY": "SPY"}, "stooq": {"SPY": "spy.us"}, "yfinance": {"SPY": "SPY"}},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "market.json"
            cache_path.write_text(
                json.dumps({"cached_at": "2026-04-03T06:00:00-07:00", "source": "cache", "data": {"SPY": {"formatted": "$123.45"}}}),
                encoding="utf-8",
            )
            outcome = client.fetch_entries(
                ["SPY"],
                cache_path=cache_path,
                fallback_builder=lambda: {"SPY": {"formatted": "stub"}},
                formatter=lambda value, ticker: f"${value:.2f}",
                yield_tickers=set(),
            )

        self.assertEqual(outcome.source, "cache")
        self.assertTrue(outcome.fallback_used)
        self.assertEqual(outcome.data["SPY"]["formatted"], "$123.45")


if __name__ == "__main__":
    unittest.main()
