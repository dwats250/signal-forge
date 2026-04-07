from __future__ import annotations

import os
import tempfile
import unittest
from urllib.error import URLError
from unittest.mock import patch

from signal_forge.data.live_fetch import (
    LiveDataUnavailableError,
    build_live_context,
    fetch_market_snapshot,
)
from signal_forge.data.providers.fmp import FMPProvider


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
        if self.reason is None:
            return filtered, [
                {"provider": self._name, "symbol": ticker, "status": "ok", "count": str(len(values))}
                for ticker, values in filtered.items()
            ]
        return filtered, [
            {
                "provider": self._name,
                "symbol": ticker,
                "status": "failed" if ticker not in filtered else "ok",
                "error_type": "ProviderError" if ticker not in filtered else None,
                "error": self.reason if ticker not in filtered else None,
                "count": str(len(filtered[ticker])) if ticker in filtered else None,
            }
            for ticker in symbol_map
        ]


class LiveFetchTests(unittest.TestCase):
    def test_fmp_provider_loads_api_key_from_repo_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")
            with open(env_path, "w", encoding="utf-8") as handle:
                handle.write("FMP_API_KEY=test-key\n")

            with patch.dict(os.environ, {"SIGNAL_FORGE_ENV_FILE": env_path}, clear=True):
                with patch("signal_forge.env._ENV_LOADED", False), patch("signal_forge.env._LOADED_ENV_PATH", None):
                    with patch("signal_forge.data.providers.fmp.urlopen", side_effect=URLError("forced")):
                        histories, diagnostics = FMPProvider().fetch_histories({"SPY": "SPY"})

        self.assertEqual(histories, {})
        self.assertEqual(diagnostics[0]["error"], "<urlopen error forced>")

    def test_fmp_provider_reloads_when_env_file_path_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            first_env = os.path.join(tmpdir, "first.env")
            second_env = os.path.join(tmpdir, "second.env")
            with open(first_env, "w", encoding="utf-8") as handle:
                handle.write("FMP_API_KEY=first-key\n")
            with open(second_env, "w", encoding="utf-8") as handle:
                handle.write("FMP_API_KEY=second-key\n")

            seen_urls: list[str] = []

            class _Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return None

                def read(self) -> bytes:
                    return b'{"historical":[{"close":100},{"close":101}]}'

            def fake_urlopen(url: str, timeout: float):
                seen_urls.append(url)
                return _Response()

            with patch("signal_forge.data.providers.fmp.urlopen", side_effect=fake_urlopen):
                with patch("signal_forge.env._ENV_LOADED", False), patch("signal_forge.env._LOADED_ENV_PATH", None):
                    with patch.dict(os.environ, {"SIGNAL_FORGE_ENV_FILE": first_env}, clear=True):
                        FMPProvider().fetch_histories({"SPY": "SPY"})
                    with patch.dict(os.environ, {"SIGNAL_FORGE_ENV_FILE": second_env}, clear=True):
                        FMPProvider().fetch_histories({"SPY": "SPY"})

        self.assertEqual(len(seen_urls), 2)
        self.assertIn("apikey=first-key", seen_urls[0])
        self.assertIn("apikey=second-key", seen_urls[1])

    def test_fmp_provider_loads_api_key_from_config_when_env_missing(self) -> None:
        seen_urls: list[str] = []

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def read(self) -> bytes:
                return b'{"historical":[{"close":100},{"close":101}]}'

        def fake_urlopen(url: str, timeout: float):
            seen_urls.append(url)
            return _Response()

        with patch("signal_forge.data.providers.fmp.urlopen", side_effect=fake_urlopen):
            with patch.dict(os.environ, {}, clear=True):
                with patch("signal_forge.data.providers.fmp.FMP_API_KEY", "config-key"):
                    FMPProvider().fetch_histories({"SPY": "SPY"})

        self.assertEqual(len(seen_urls), 1)
        self.assertIn("apikey=config-key", seen_urls[0])

    def test_fmp_provider_normalizes_raw_list_payload(self) -> None:
        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def read(self) -> bytes:
                return b'[{"close":100},{"close":101},{"close":102}]'

        with patch("signal_forge.data.providers.fmp.urlopen", return_value=_Response()):
            with patch.dict(os.environ, {"FMP_API_KEY": "test-key"}, clear=True):
                histories, diagnostics = FMPProvider().fetch_histories({"SPY": "SPY"})

        self.assertEqual(histories, {"SPY": [102.0, 101.0, 100.0]})
        self.assertEqual(diagnostics, [{"provider": "fmp", "symbol": "SPY", "status": "ok", "count": "3"}])

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
        self.assertEqual(snapshot["_meta"]["mode"], "full")

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

    def test_fetch_market_snapshot_allows_degraded_mode_when_optional_groups_are_missing(self) -> None:
        snapshot = fetch_market_snapshot(
            providers=[
                FakeProvider(
                    "fmp",
                    histories={
                        "SPY": [100, 101, 102, 103, 104, 105],
                        "QQQ": [200, 201, 202, 203, 204, 205],
                        "IWM": [50, 50.5, 51, 51.5, 52, 52.5],
                        "VIX": [20, 19.5, 19, 18.5, 18, 17.5],
                    },
                ),
                FakeProvider("stooq", histories={}, reason="stooq down"),
            ]
        )

        self.assertEqual(snapshot["_meta"]["mode"], "degraded")
        self.assertEqual(snapshot["_meta"]["decision"], "proceed")
        self.assertIn("fx", snapshot["_meta"]["missing_groups"])
        self.assertIn("rates", snapshot["_meta"]["missing_groups"])

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
