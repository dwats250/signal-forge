from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from signal_forge.data.unified_data import (
    UnifiedMarketDataClient,
    classify_core_macro_health,
    compute_data_confidence,
    validate_data_point,
)


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


class FakeCache:
    def __init__(self, payload: dict | None = None, symbol_payloads: dict[str, dict] | None = None):
        self.payload = payload
        self.symbol_payloads = symbol_payloads or {}
        self.saved_symbols: dict[str, dict] = {}

    def load(self, path: Path) -> dict | None:
        return self.payload

    def save(self, path: Path, payload: dict) -> None:
        self.payload = payload.get("data")

    def load_symbol(self, symbol: str) -> dict | None:
        return self.symbol_payloads.get(symbol)

    def save_symbol(self, symbol: str, value: dict, timestamp: str) -> None:
        self.saved_symbols[symbol] = {"value": value, "timestamp": timestamp}


class UnifiedDataTests(unittest.TestCase):
    def test_fetch_entries_uses_stooq_after_fmp_failure(self) -> None:
        cache = FakeCache()
        client = UnifiedMarketDataClient(
            providers=[
                FakeProvider("fmp", {}, "fmp down"),
                FakeProvider("stooq", {"SPY": [100.0, 101.0, 102.0]}),
            ],
            cache=cache,
            provider_symbols={
                "fmp": {"SPY": "SPY"},
                "stooq": {"SPY": "spy.us"},
            },
        )

        outcome = client.fetch_entries(
            ["SPY"],
            cache_path=Path("/tmp/market.json"),
            fallback_builder=lambda: {"SPY": {"price": 99.0, "formatted": "$99.00"}},
            formatter=lambda value, ticker: f"${value:.2f}",
            yield_tickers=set(),
        )

        self.assertEqual(outcome.source, "stooq")
        self.assertTrue(outcome.fallback_used)
        self.assertEqual(outcome.data["SPY"]["formatted"], "$102.00")
        self.assertEqual(outcome.data["SPY"]["source"], "stooq")
        self.assertTrue(outcome.data["SPY"]["valid"])
        self.assertEqual(outcome.data["_meta"]["confidence_score"], 10)
        self.assertIn("SPY", cache.saved_symbols)

    def test_fetch_entries_falls_back_to_fresh_symbol_cache(self) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        cache = FakeCache(
            symbol_payloads={
                "SPY": {
                    "symbol": "SPY",
                    "timestamp": timestamp,
                    "source": "cache",
                    "value": {
                        "price": 123.45,
                        "day_chg": 1.0,
                        "week_chg": 2.0,
                        "formatted": "$123.45",
                        "is_yield": False,
                        "timestamp": timestamp,
                    },
                }
            }
        )
        client = UnifiedMarketDataClient(
            providers=[FakeProvider("fmp", {}, "fmp down"), FakeProvider("stooq", {}, "stooq down")],
            cache=cache,
            provider_symbols={"fmp": {"SPY": "SPY"}, "stooq": {"SPY": "spy.us"}},
        )

        outcome = client.fetch_entries(
            ["SPY"],
            cache_path=Path("/tmp/market.json"),
            fallback_builder=lambda: {"SPY": {"price": 99.0, "formatted": "$99.00"}},
            formatter=lambda value, ticker: f"${value:.2f}",
            yield_tickers=set(),
        )

        self.assertEqual(outcome.source, "cache")
        self.assertTrue(outcome.fallback_used)
        self.assertEqual(outcome.data["SPY"]["formatted"], "$123.45")
        self.assertTrue(outcome.data["SPY"]["valid"])

    def test_fetch_entries_rejects_stale_cache_and_uses_stub(self) -> None:
        stale_timestamp = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
        cache = FakeCache(
            symbol_payloads={
                "SPY": {
                    "symbol": "SPY",
                    "timestamp": stale_timestamp,
                    "source": "cache",
                    "value": {
                        "price": 123.45,
                        "day_chg": 1.0,
                        "week_chg": 2.0,
                        "formatted": "$123.45",
                        "is_yield": False,
                        "timestamp": stale_timestamp,
                    },
                }
            }
        )
        client = UnifiedMarketDataClient(
            providers=[FakeProvider("fmp", {}, "fmp down"), FakeProvider("stooq", {}, "stooq down")],
            cache=cache,
            provider_symbols={"fmp": {"SPY": "SPY"}, "stooq": {"SPY": "spy.us"}},
        )

        outcome = client.fetch_entries(
            ["SPY"],
            cache_path=Path("/tmp/market.json"),
            fallback_builder=lambda: {"SPY": {"price": 99.0, "day_chg": 0.0, "week_chg": 0.0, "formatted": "$99.00"}},
            formatter=lambda value, ticker: f"${value:.2f}",
            yield_tickers=set(),
        )

        self.assertEqual(outcome.data["SPY"]["source"], "stub")
        self.assertFalse(outcome.data["SPY"]["valid"])
        self.assertEqual(outcome.data["SPY"]["source_label"], "DEGRADED STUB")

    def test_validate_data_point_rejects_missing_and_stale_values(self) -> None:
        fresh = datetime.now(timezone.utc).isoformat()
        stale = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        self.assertTrue(validate_data_point(1.0, fresh))
        self.assertFalse(validate_data_point(None, fresh))
        self.assertFalse(validate_data_point(1.0, stale))

    def test_compute_data_confidence_uses_weighted_core_fields(self) -> None:
        data = {
            "DXY": {"valid": True},
            "US10Y": {"valid": True},
            "VIX": {"valid": False},
            "WTI": {"valid": True},
            "GOLD": {"valid": False},
            "SILVER": {"valid": True},
            "SPY": {"valid": True},
        }
        self.assertEqual(compute_data_confidence(data), 75)

    def test_classify_core_macro_health_distinguishes_healthy_degraded_and_blind(self) -> None:
        healthy = {
            "DXY": {"valid": True},
            "US10Y": {"valid": True},
            "VIX": {"valid": True},
            "WTI": {"valid": True},
            "GOLD": {"valid": True},
            "SILVER": {"valid": True},
            "SPY": {"valid": True},
        }
        degraded = {
            **healthy,
            "VIX": {"valid": False},
        }
        blind = {
            "DXY": {"valid": False},
            "US10Y": {"valid": False},
            "VIX": {"valid": False},
            "WTI": {"valid": False},
            "GOLD": {"valid": False},
            "SILVER": {"valid": False},
            "SPY": {"valid": True},
        }

        self.assertEqual(classify_core_macro_health(healthy), "healthy")
        self.assertEqual(classify_core_macro_health(degraded), "degraded")
        self.assertEqual(classify_core_macro_health(blind), "blind")


if __name__ == "__main__":
    unittest.main()
