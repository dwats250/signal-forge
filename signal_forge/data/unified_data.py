from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from signal_forge.data.cache import JsonDataCache
from signal_forge.data.providers import FMPProvider, StooqProvider, YFinanceProvider

DATA_SOURCE_UNAVAILABLE = "DATA_SOURCE_UNAVAILABLE"

DEFAULT_PROVIDER_SYMBOLS: dict[str, dict[str, str]] = {
    "fmp": {
        "SPY": "SPY",
        "QQQ": "QQQ",
        "TSLA": "TSLA",
        "MU": "MU",
        "OXY": "OXY",
        "XLE": "XLE",
        "GDX": "GDX",
        "NEM": "NEM",
        "WPM": "WPM",
    },
    "stooq": {
        "SPY": "spy.us",
        "QQQ": "qqq.us",
        "TSLA": "tsla.us",
        "MU": "mu.us",
        "OXY": "oxy.us",
        "XLE": "xle.us",
        "GDX": "gdx.us",
        "NEM": "nem.us",
        "WPM": "wpm.us",
    },
    "yfinance": {
        "DXY": "DX-Y.NYB",
        "US10Y": "^TNX",
        "WTI": "CL=F",
        "GOLD": "GC=F",
        "SILVER": "SI=F",
        "COPPER": "HG=F",
        "PLATINUM": "PL=F",
        "PALLADIUM": "PA=F",
        "SPY": "SPY",
        "QQQ": "QQQ",
        "BTC": "BTC-USD",
        "VIX": "^VIX",
        "XLE": "XLE",
        "OXY": "OXY",
        "GDX": "GDX",
        "NEM": "NEM",
        "WPM": "WPM",
        "TSLA": "TSLA",
        "MU": "MU",
    },
}


class HistoryProvider(Protocol):
    @property
    def name(self) -> str: ...

    def fetch_histories(self, symbol_map: dict[str, str]) -> tuple[dict[str, list[float]], str | None]: ...


@dataclass
class FetchOutcome:
    data: dict
    source: str
    fallback_used: bool
    reason: str | None = None


class UnifiedMarketDataClient:
    """Single entry point for provider selection and fallback policy."""

    def __init__(
        self,
        providers: list[HistoryProvider] | None = None,
        cache: JsonDataCache | None = None,
        provider_symbols: dict[str, dict[str, str]] | None = None,
    ) -> None:
        self.providers = providers or [FMPProvider(), StooqProvider(), YFinanceProvider()]
        self.cache = cache or JsonDataCache()
        self.provider_symbols = provider_symbols or DEFAULT_PROVIDER_SYMBOLS

    def fetch_entries(
        self,
        tickers: list[str],
        *,
        cache_path: Path,
        fallback_builder: Callable[[], dict],
        formatter: Callable[[float, str], str],
        yield_tickers: set[str],
    ) -> FetchOutcome:
        for provider in self.providers:
            symbol_map = self._symbol_map_for(provider.name, tickers)
            if not symbol_map:
                continue

            histories, reason = provider.fetch_histories(symbol_map)
            if histories:
                return FetchOutcome(
                    data=self._build_entries(tickers, histories, formatter, yield_tickers),
                    source=provider.name,
                    fallback_used=False,
                    reason=reason,
                )

        cached = self.cache.load(cache_path)
        if cached is not None:
            return FetchOutcome(cached, "cache", True, DATA_SOURCE_UNAVAILABLE)

        return FetchOutcome(fallback_builder(), "stub", True, DATA_SOURCE_UNAVAILABLE)

    def fetch_series(
        self,
        symbol: str,
        *,
        fallback_builder: Callable[[str], list[float]],
    ) -> list[float]:
        tickers = [symbol]
        for provider in self.providers:
            symbol_map = self._symbol_map_for(provider.name, tickers)
            if not symbol_map:
                continue
            histories, _reason = provider.fetch_histories(symbol_map)
            series = histories.get(symbol)
            if series:
                return series
        return fallback_builder(symbol)

    def _symbol_map_for(self, provider_name: str, tickers: list[str]) -> dict[str, str]:
        symbol_lookup = self.provider_symbols.get(provider_name, {})
        return {
            ticker: symbol_lookup.get(ticker, ticker)
            for ticker in tickers
        }

    def _build_entries(
        self,
        tickers: list[str],
        histories: dict[str, list[float]],
        formatter: Callable[[float, str], str],
        yield_tickers: set[str],
    ) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for ticker in tickers:
            closes = histories.get(ticker, [])
            if len(closes) < 2:
                result[ticker] = self._missing_market_entry(is_yield=ticker in yield_tickers)
                continue

            current = float(closes[-1])
            prev = float(closes[-2])
            week_ago = float(closes[-6]) if len(closes) >= 6 else float(closes[0])

            if ticker in yield_tickers:
                day_chg = (current - prev) * 100
                week_chg = (current - week_ago) * 100
            else:
                day_chg = (current - prev) / prev * 100
                week_chg = (current - week_ago) / week_ago * 100

            result[ticker] = {
                "price": current,
                "day_chg": round(day_chg, 2),
                "week_chg": round(week_chg, 2),
                "formatted": formatter(current, ticker),
                "is_yield": ticker in yield_tickers,
            }
        return result

    def _missing_market_entry(self, *, is_yield: bool = False) -> dict:
        return {
            "price": None,
            "day_chg": None,
            "week_chg": None,
            "formatted": "Source unavailable",
            "is_yield": is_yield,
            "source_unavailable": True,
        }
