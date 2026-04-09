from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reports import morning_edge
from signal_forge.data import commodity_resolver
from signal_forge.data.unified_data import FetchOutcome


class MorningEdgeMarketDataTests(unittest.TestCase):
    def setUp(self) -> None:
        commodity_resolver.LAST_GOOD.clear()

    def test_get_macro_bundle_returns_dashboard_bundle(self) -> None:
        market_data = {
            "DXY": {"price": 100.0, "day_chg": 0.5, "week_chg": 1.0, "formatted": "100.00", "is_yield": False},
            "US10Y": {"price": 4.25, "day_chg": 5.0, "week_chg": 10.0, "formatted": "4.25%", "is_yield": True},
            "REAL10Y": {"price": 2.05, "day_chg": 5.0, "week_chg": 10.0, "formatted": "2.05%", "is_yield": True, "estimated": True},
            "WTI": {"price": 80.0, "day_chg": 1.0, "week_chg": 2.0, "formatted": "$80.00", "is_yield": False},
            "GOLD": {"price": 2400.0, "day_chg": 0.4, "week_chg": 1.2, "formatted": "$2400.00", "is_yield": False},
            "SILVER": {"price": 30.0, "day_chg": 0.8, "week_chg": 1.6, "formatted": "$30.00", "is_yield": False},
            "SPY": {"price": 510.0, "day_chg": 0.3, "week_chg": 0.9, "formatted": "$510.00", "is_yield": False},
            "QQQ": {"price": 430.0, "day_chg": 0.5, "week_chg": 1.1, "formatted": "$430.00", "is_yield": False},
            "BTC": {"price": 68000.0, "day_chg": 1.0, "week_chg": 4.0, "formatted": "$68,000", "is_yield": False},
            "VIX": {"price": 15.0, "day_chg": -1.0, "week_chg": -3.0, "formatted": "15.0", "is_yield": False},
            "XLE": {"price": 95.0, "day_chg": 0.2, "week_chg": 0.7, "formatted": "$95.00", "is_yield": False},
            "OXY": {"price": 67.0, "day_chg": 0.4, "week_chg": 1.0, "formatted": "$67.00", "is_yield": False},
            "GDX": {"price": 34.0, "day_chg": 0.6, "week_chg": 1.3, "formatted": "$34.00", "is_yield": False},
            "NEM": {"price": 36.0, "day_chg": 0.5, "week_chg": 1.0, "formatted": "$36.00", "is_yield": False},
            "WPM": {"price": 48.0, "day_chg": 0.7, "week_chg": 1.4, "formatted": "$48.00", "is_yield": False},
            "TSLA": {"price": 170.0, "day_chg": -0.3, "week_chg": -1.0, "formatted": "$170.00", "is_yield": False},
            "MU": {"price": 124.0, "day_chg": 0.9, "week_chg": 2.5, "formatted": "$124.00", "is_yield": False},
        }
        narrative = morning_edge._stub_narrative(market_data)

        with patch("reports.morning_edge.fetch_market_data", return_value=market_data):
            with patch("reports.morning_edge._stub_narrative", return_value=narrative):
                bundle = morning_edge.get_macro_bundle(offline=True)

        self.assertEqual(bundle["market_data"], market_data)
        self.assertIn("macro_bar", bundle)
        self.assertIn("financial_plumbing", bundle)
        self.assertIn("metals", bundle)
        self.assertIn("equities", bundle)

    def test_fetch_market_data_uses_cache_after_live_failure(self) -> None:
        cached = {"SPY": {"price": 123.45, "formatted": "$123.45"}, "_meta": {"confidence_score": 10}}
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "market_data.latest.json"
            cache_path.write_text(
                json.dumps({"cached_at": "2026-04-03T06:00:00-07:00", "source": "yfinance", "data": cached}),
                encoding="utf-8",
            )
            with patch.object(morning_edge, "MARKET_CACHE_PATH", cache_path):
                with patch(
                    "reports.morning_edge.UnifiedMarketDataClient.fetch_entries",
                    return_value=FetchOutcome(cached, "cache", True, "DATA_SOURCE_UNAVAILABLE"),
                ):
                    data = morning_edge.fetch_market_data()

        self.assertEqual(data["SPY"]["formatted"], "$123.45")
        self.assertEqual(data["_meta"]["confidence_score"], 10)
        self.assertIn("REAL10Y", data)

    def test_fetch_market_data_uses_stub_without_live_or_cache(self) -> None:
        stub = morning_edge.build_stub_market_data()
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "missing.json"
            with patch.object(morning_edge, "MARKET_CACHE_PATH", cache_path):
                with patch(
                    "reports.morning_edge.UnifiedMarketDataClient.fetch_entries",
                    return_value=FetchOutcome(stub, "stub", True, "DATA_SOURCE_UNAVAILABLE"),
                ):
                    data = morning_edge.fetch_market_data()

        self.assertEqual(data["DXY"]["formatted"], stub["DXY"]["formatted"])
        self.assertIn("_meta", data)
        self.assertIn("REAL10Y", data)

    def test_fetch_market_data_invalidates_out_of_range_gold(self) -> None:
        invalid = {
            "GOLD": {"price": 18.04, "day_chg": 0.4, "week_chg": 1.8, "formatted": "$18.04", "is_yield": False},
            "SILVER": {"price": 26.11, "day_chg": 0.6, "week_chg": 2.2, "formatted": "$26.11", "is_yield": False},
            "US10Y": {"price": 4.21, "day_chg": 4.0, "week_chg": 11.0, "formatted": "4.21%", "is_yield": True},
        }

        with patch(
            "reports.morning_edge.UnifiedMarketDataClient.fetch_entries",
            return_value=FetchOutcome(invalid, "fmp", False, None),
        ):
            data = morning_edge.fetch_market_data()

        self.assertIsNone(data["GOLD"]["price"])
        self.assertEqual(data["GOLD"]["formatted"], "DATA UNAVAILABLE")
        self.assertTrue(data["GOLD"]["source_unavailable"])
        self.assertIn("REAL10Y", data)

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

    def test_build_metals_context_renders_unavailable_gold_cleanly(self) -> None:
        md = {
            "GOLD": {"price": None, "formatted": "DATA UNAVAILABLE", "source_unavailable": True},
            "SILVER": {"price": 30.0, "formatted": "$30.00"},
            "REAL10Y": {"price": 2.0, "formatted": "2.00%", "is_yield": True},
        }

        metals = morning_edge._build_metals_context(md)

        self.assertEqual(metals["cards"][0]["entry"]["formatted"], "DATA UNAVAILABLE")
        self.assertEqual(metals["gold_silver_ratio"], "Unavailable")

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
        self.assertIn("badge_text", plumbing[0])

    def test_build_report_data_exposes_confidence_badge_and_banner(self) -> None:
        market_data = morning_edge.build_stub_market_data()
        market_data["_meta"] = {"confidence_score": 68, "core_macro_health": "blind", "fallback_symbols": ["DXY", "US10Y"]}

        report_data = morning_edge.build_report_data(market_data, morning_edge._stub_narrative(market_data))

        self.assertEqual(report_data["confidence_score"], 68)
        self.assertEqual(report_data["confidence_badge_tone"], "red")
        self.assertTrue(report_data["show_low_confidence_banner"])
        self.assertEqual(report_data["healthcheck"]["core_macro_status"], "blind")

    def test_render_html_includes_healthcheck_panel_and_fallback_symbols(self) -> None:
        market_data = morning_edge.build_stub_market_data()
        market_data["_meta"] = {"confidence_score": 48, "core_macro_health": "blind", "fallback_symbols": ["DXY", "US10Y"]}
        report_data = morning_edge.build_report_data(market_data, morning_edge._stub_narrative(market_data))
        report_data["healthcheck"] = {
            "build_status": "FAILURE",
            "build_status_tone": "red",
            "data_confidence_score": 48,
            "core_macro_status": "blind",
            "core_macro_tone": "red",
            "execution_mode": "NO_TRADE",
            "execution_mode_tone": "red",
            "setup_counts": {"ready": 0, "watchlist": 0, "blocked": 2},
            "fallback_symbols": ["DXY", "US10Y"],
            "top_block_reason": "CORE_MACRO_BLIND",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "morning_edge.html"
            morning_edge.render_html(report_data, out_path=out_path)
            html = out_path.read_text(encoding="utf-8")

        self.assertIn("System Healthcheck", html)
        self.assertIn("FAILURE", html)
        self.assertIn("NO_TRADE", html)
        self.assertIn("CORE_MACRO_BLIND", html)
        self.assertIn("Fallback: DXY, US10Y", html)

    def test_generate_narrative_falls_back_on_invalid_json(self) -> None:
        market_data = morning_edge.build_stub_market_data()

        class _FakeContent:
            text = '{"summary":"broken'

        class _FakeResponse:
            content = [_FakeContent()]

        class _FakeMessages:
            @staticmethod
            def create(**_: object) -> _FakeResponse:
                return _FakeResponse()

        class _FakeClient:
            def __init__(self, api_key: str) -> None:
                self.api_key = api_key
                self.messages = _FakeMessages()

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            with patch("reports.morning_edge.anthropic.Anthropic", _FakeClient):
                narrative = morning_edge.generate_narrative(market_data)

        self.assertEqual(narrative, morning_edge._stub_narrative(market_data))

    def test_generate_narrative_falls_back_to_stub_when_anthropic_is_unreachable(self) -> None:
        market_data = morning_edge.build_stub_market_data()
        stub_narrative = morning_edge._stub_narrative(market_data)

        class _FailingMessages:
            @staticmethod
            def create(**_: object) -> object:
                raise RuntimeError("network unavailable")

        class _FakeClient:
            def __init__(self, api_key: str) -> None:
                self.api_key = api_key
                self.messages = _FailingMessages()

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            with patch("reports.morning_edge.anthropic.Anthropic", _FakeClient):
                narrative = morning_edge.generate_narrative(market_data)

        self.assertEqual(narrative, stub_narrative)

    def test_generate_narrative_retries_before_stub_fallback(self) -> None:
        market_data = morning_edge.build_stub_market_data()
        attempts: list[int] = []

        class _FailingMessages:
            @staticmethod
            def create(**_: object) -> object:
                attempts.append(1)
                raise RuntimeError("still unavailable")

        class _FakeClient:
            def __init__(self, api_key: str) -> None:
                self.api_key = api_key
                self.messages = _FailingMessages()

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            with patch("reports.morning_edge.anthropic.Anthropic", _FakeClient):
                narrative = morning_edge.generate_narrative(market_data)

        self.assertEqual(len(attempts), morning_edge.NARRATIVE_RETRY_ATTEMPTS)
        self.assertEqual(narrative, morning_edge._stub_narrative(market_data))


if __name__ == "__main__":
    unittest.main()
