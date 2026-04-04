from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
