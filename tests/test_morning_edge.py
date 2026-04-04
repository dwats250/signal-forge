from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from reports import morning_edge


class MorningEdgeMarketDataTests(unittest.TestCase):
    def test_fetch_market_data_uses_cache_after_live_failure(self) -> None:
        cached = {"SPY": {"price": 123.45, "formatted": "$123.45"}}
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "market_data.latest.json"
            cache_path.write_text(
                json.dumps({"cached_at": "2026-04-03T06:00:00-07:00", "source": "yfinance", "data": cached}),
                encoding="utf-8",
            )
            with patch.object(morning_edge, "MARKET_CACHE_PATH", cache_path):
                with patch("reports.morning_edge.yf.download", side_effect=RuntimeError("dns failed")):
                    data = morning_edge.fetch_market_data()

        self.assertEqual(data, cached)

    def test_fetch_market_data_uses_stub_without_live_or_cache(self) -> None:
        stub = morning_edge.build_stub_market_data()
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "missing.json"
            with patch.object(morning_edge, "MARKET_CACHE_PATH", cache_path):
                with patch("reports.morning_edge.yf.download", side_effect=RuntimeError("dns failed")):
                    data = morning_edge.fetch_market_data()

        self.assertEqual(data, stub)

    def test_save_market_data_cache_writes_payload(self) -> None:
        sample = {"SPY": {"price": 123.45, "formatted": "$123.45"}}
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "market_data.latest.json"
            output_dir = Path(tmpdir)
            with patch.object(morning_edge, "OUTPUT_DIR", output_dir):
                with patch.object(morning_edge, "MARKET_CACHE_PATH", cache_path):
                    morning_edge.save_market_data_cache(sample)

            payload = json.loads(cache_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["data"], sample)
        self.assertEqual(payload["source"], "yfinance")
        self.assertIn("cached_at", payload)

    def test_fetch_market_data_recovers_missing_symbol_with_single_symbol_fallback(self) -> None:
        closes = pd.DataFrame(
            {
                "GC=F": [2300.0, 2310.0, 2320.0],
                "SI=F": [None, None, None],
            }
        )
        fallback = pd.DataFrame({"Close": [28.0, 29.0, 30.0]})

        def fake_download(*args, **kwargs):
            ticker = kwargs.get("tickers")
            if ticker == "SI=F":
                return fallback
            return {"Close": closes}

        with patch("reports.morning_edge.yf.download", side_effect=fake_download):
            data = morning_edge.fetch_market_data()

        self.assertEqual(data["SILVER"]["formatted"], "$30.00")
        self.assertFalse(data["SILVER"].get("source_unavailable", False))

    def test_build_metals_context_includes_ratio_and_explicit_inventory_fallbacks(self) -> None:
        md = {
            "GOLD": {"price": 2400.0, "formatted": "$2400.00"},
            "SILVER": {"price": 30.0, "formatted": "$30.00"},
            "REAL10Y": {"price": 2.0, "formatted": "2.00%", "is_yield": True},
        }

        metals = morning_edge._build_metals_context(md)

        self.assertEqual(metals["gold_silver_ratio"], "80.00")
        self.assertIn("COMEX silver front month: $30.00", metals["inventory_lines"])
        self.assertIn("Shanghai silver reference: Shanghai data not yet integrated", metals["inventory_lines"])
        self.assertIn("Warehouse / exchange inventory: Inventory data coming soon", metals["inventory_lines"])

    def test_build_financial_plumbing_includes_value_and_change_fields(self) -> None:
        md = {
            "DXY": {"price": 100.0, "day_chg": 0.5, "formatted": "100.00", "is_yield": False},
            "US10Y": {"price": 4.25, "day_chg": 5.0, "formatted": "4.25%", "is_yield": True},
            "VIX": {"price": 18.0, "day_chg": -2.0, "formatted": "18.0", "is_yield": False},
            "WTI": {"price": 80.0, "day_chg": 1.25, "formatted": "$80.00", "is_yield": False},
            "GOLD": {"price": 2400.0, "day_chg": 0.4, "formatted": "$2400.00", "is_yield": False},
            "SILVER": {"price": 30.0, "day_chg": -0.5, "formatted": "$30.00", "is_yield": False},
        }

        plumbing = morning_edge._build_financial_plumbing(md)

        self.assertEqual([item["label"] for item in plumbing], ["DXY", "US 10Y", "VIX", "Oil", "Gold", "Silver"])
        self.assertEqual(plumbing[1]["absolute_change"], "+0.05 pts")
        self.assertEqual(plumbing[1]["percent_change"], "+5bps")
        self.assertEqual(plumbing[5]["direction"], "down")


if __name__ == "__main__":
    unittest.main()
