from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from signal_forge.data.cache import JsonDataCache
from signal_forge.data.providers import FMPProvider, StooqProvider

DATA_SOURCE_UNAVAILABLE = "DATA_SOURCE_UNAVAILABLE"
VALIDATION_WINDOW_HOURS = 24
CRITICAL_DATA_SYMBOLS = ("DXY", "US10Y", "VIX")
CONFIDENCE_WEIGHTS: dict[str, int] = {
    "DXY": 20,
    "US10Y": 20,
    "VIX": 15,
    "WTI": 15,
    "GOLD": 10,
    "SILVER": 10,
    "SPY": 10,
}

DEFAULT_PROVIDER_SYMBOLS: dict[str, dict[str, str]] = {
    "fmp": {
        "DXY": "UUP",
        "US10Y": "TLT",
        "WTI": "USO",
        "GOLD": "XAUUSD",
        "SILVER": "SLV",
        "SPY": "SPY",
        "QQQ": "QQQ",
        "BTC": "IBIT",
        "VIX": "VIXY",
        "XLE": "XLE",
        "OXY": "OXY",
        "GDX": "GDX",
        "NEM": "NEM",
        "WPM": "WPM",
        "TSLA": "TSLA",
        "MU": "MU",
    },
    "stooq": {
        "DXY": "uup.us",
        "US10Y": "tlt.us",
        "WTI": "uso.us",
        "GOLD": "xauusd",
        "SILVER": "slv.us",
        "SPY": "spy.us",
        "QQQ": "qqq.us",
        "BTC": "ibit.us",
        "VIX": "vixy.us",
        "XLE": "xle.us",
        "OXY": "oxy.us",
        "GDX": "gdx.us",
        "NEM": "nem.us",
        "WPM": "wpm.us",
        "TSLA": "tsla.us",
        "MU": "mu.us",
    },
}


class HistoryProvider(Protocol):
    @property
    def name(self) -> str: ...

    def fetch_histories(self, symbol_map: dict[str, str]) -> tuple[dict[str, list[float]], object]: ...


@dataclass
class FetchOutcome:
    data: dict
    source: str
    fallback_used: bool
    reason: str | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def validate_data_point(value: object, timestamp: object) -> bool:
    if value is None:
        return False
    parsed = _coerce_timestamp(timestamp)
    if parsed is None:
        return False
    age_seconds = (_utc_now() - parsed).total_seconds()
    return 0 <= age_seconds <= VALIDATION_WINDOW_HOURS * 3600


def compute_data_confidence(data: dict[str, dict]) -> int:
    total = 0
    score = 0
    for key, weight in CONFIDENCE_WEIGHTS.items():
        total += weight
        entry = data.get(key) or data.get("OIL" if key == "WTI" else key) or {}
        if bool(entry.get("valid")):
            score += weight
    return int((score / total) * 100) if total else 0


class UnifiedMarketDataClient:
    """Single entry point for provider selection and fallback policy."""

    def __init__(
        self,
        providers: list[HistoryProvider] | None = None,
        cache: JsonDataCache | None = None,
        provider_symbols: dict[str, dict[str, str]] | None = None,
    ) -> None:
        self.providers = providers or [FMPProvider(), StooqProvider()]
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
        fallback_data = fallback_builder()
        result: dict[str, dict] = {}
        sources: list[str] = []
        reasons: list[str] = []
        fallback_used = False

        for ticker in tickers:
            entry, source, used_fallback, reason = self.fetch_with_fallback(
                ticker,
                cache_path=cache_path,
                fallback_data=fallback_data,
                formatter=formatter,
                is_yield=ticker in yield_tickers,
            )
            result[ticker] = entry
            sources.append(source)
            fallback_used = fallback_used or used_fallback
            if reason:
                reasons.append(reason)

        confidence_score = compute_data_confidence(result)
        critical_missing = [ticker for ticker in CRITICAL_DATA_SYMBOLS if not bool(result.get(ticker, {}).get("valid"))]
        fail_safe_no_trade = len(critical_missing) == len(CRITICAL_DATA_SYMBOLS)
        result["_meta"] = {
            "confidence_score": confidence_score,
            "critical_missing": critical_missing,
            "fail_safe_no_trade": fail_safe_no_trade,
            "fetched_at": _utc_now().isoformat(),
            "sources": sorted(set(sources)),
        }

        if any(source not in {"cache", "stub", "unavailable"} for source in sources):
            self.cache.save(cache_path, {"cached_at": _utc_now().isoformat(), "source": "mixed", "data": result})

        resolved_source = sources[0] if len(set(sources)) == 1 else "mixed"
        return FetchOutcome(result, resolved_source, fallback_used, "; ".join(reasons) or None)

    def fetch_with_fallback(
        self,
        symbol: str,
        *,
        cache_path: Path,
        fallback_data: dict,
        formatter: Callable[[float, str], str],
        is_yield: bool,
    ) -> tuple[dict, str, bool, str | None]:
        reasons: list[str] = []
        for provider_name in ("fmp", "stooq"):
            provider = self._provider_by_name(provider_name)
            if provider is None:
                continue
            symbol_map = self._symbol_map_for(provider_name, [symbol])
            provider_symbol = symbol_map.get(symbol)
            if not provider_symbol:
                reasons.append(f"{provider_name}:{symbol} unavailable")
                continue
            histories, reason = provider.fetch_histories({symbol: provider_symbol})
            series = histories.get(symbol)
            if series and len(series) >= 2:
                entry = self._build_market_entry(symbol, series, formatter, is_yield, source=provider_name)
                self.cache.save_symbol(symbol, entry, entry["timestamp"])
                return entry, provider_name, provider_name != "fmp", self._stringify_reason(reason)
            if reason is not None:
                reasons.append(f"{provider_name}:{self._stringify_reason(reason) or DATA_SOURCE_UNAVAILABLE}")

        cached = self.cache.load_symbol(symbol)
        if cached is not None and isinstance(cached.get("value"), dict):
            entry = dict(cached["value"])
            entry["source"] = "cache"
            entry["cache_timestamp"] = cached["timestamp"]
            entry["timestamp"] = str(entry.get("timestamp") or cached["timestamp"])
            entry["valid"] = validate_data_point(entry.get("price"), entry.get("timestamp"))
            if entry["valid"]:
                entry["source_label"] = "CACHED VALUE"
                return entry, "cache", True, "; ".join(reasons) or DATA_SOURCE_UNAVAILABLE

        legacy_cache = self.cache.load(cache_path) or {}
        legacy_entry = legacy_cache.get(symbol)
        if isinstance(legacy_entry, dict):
            timestamp = str(legacy_entry.get("timestamp") or legacy_cache.get("_meta", {}).get("fetched_at") or "")
            if validate_data_point(legacy_entry.get("price"), timestamp):
                entry = dict(legacy_entry)
                entry["source"] = "cache"
                entry["timestamp"] = timestamp
                entry["valid"] = True
                entry["source_label"] = "CACHED VALUE"
                return entry, "cache", True, "; ".join(reasons) or DATA_SOURCE_UNAVAILABLE

        fallback_entry = fallback_data.get(symbol)
        if isinstance(fallback_entry, dict):
            entry = self._normalize_fallback_entry(symbol, fallback_entry, formatter, is_yield)
            return entry, str(entry.get("source", "stub")), True, "; ".join(reasons) or DATA_SOURCE_UNAVAILABLE

        return self._missing_market_entry(is_yield=is_yield), "unavailable", True, "; ".join(reasons) or DATA_SOURCE_UNAVAILABLE

    def fetch_series(
        self,
        symbol: str,
        *,
        fallback_builder: Callable[[str], list[float]],
    ) -> list[float]:
        for provider_name in ("fmp", "stooq"):
            provider = self._provider_by_name(provider_name)
            if provider is None:
                continue
            symbol_map = self._symbol_map_for(provider_name, [symbol])
            provider_symbol = symbol_map.get(symbol)
            if not provider_symbol:
                continue
            histories, _reason = provider.fetch_histories({symbol: provider_symbol})
            series = histories.get(symbol)
            if series:
                return series
        return fallback_builder(symbol)

    def _provider_by_name(self, provider_name: str) -> HistoryProvider | None:
        for provider in self.providers:
            if provider.name == provider_name:
                return provider
        return None

    def _stringify_reason(self, reason: object) -> str | None:
        if reason is None:
            return None
        if isinstance(reason, str):
            return reason
        if isinstance(reason, list):
            failures = [item for item in reason if isinstance(item, dict) and item.get("status") != "ok"]
            if not failures:
                return None
            first = failures[0]
            error = first.get("error") or "provider data unavailable"
            symbol = first.get("symbol")
            return f"{symbol}: {error}" if symbol else str(error)
        return str(reason)

    def _symbol_map_for(self, provider_name: str, tickers: list[str]) -> dict[str, str]:
        symbol_lookup = self.provider_symbols.get(provider_name, {})
        return {ticker: symbol_lookup.get(ticker, "") for ticker in tickers}

    def _build_market_entry(
        self,
        ticker: str,
        closes: list[float],
        formatter: Callable[[float, str], str],
        is_yield: bool,
        *,
        source: str,
    ) -> dict:
        current = float(closes[-1])
        prev = float(closes[-2])
        week_ago = float(closes[-6]) if len(closes) >= 6 else float(closes[0])
        if is_yield:
            day_chg = (current - prev) * 100
            week_chg = (current - week_ago) * 100
        else:
            day_chg = (current - prev) / prev * 100
            week_chg = (current - week_ago) / week_ago * 100
        timestamp = _utc_now().isoformat()
        return {
            "price": current,
            "day_chg": round(day_chg, 2),
            "week_chg": round(week_chg, 2),
            "formatted": formatter(current, ticker),
            "is_yield": is_yield,
            "source": source,
            "source_label": "PRIMARY: FMP" if source == "fmp" else "FALLBACK SOURCE (STOOQ)",
            "timestamp": timestamp,
            "valid": validate_data_point(current, timestamp),
            "source_unavailable": False,
        }

    def _normalize_fallback_entry(
        self,
        ticker: str,
        entry: dict,
        formatter: Callable[[float, str], str],
        is_yield: bool,
    ) -> dict:
        normalized = dict(entry)
        price = normalized.get("price")
        if isinstance(price, (int, float)):
            normalized["formatted"] = formatter(float(price), ticker)
        normalized["is_yield"] = normalized.get("is_yield", is_yield)
        normalized["source"] = normalized.get("source", "stub")
        normalized["source_label"] = "DEGRADED STUB"
        normalized["timestamp"] = str(normalized.get("timestamp") or _utc_now().isoformat())
        normalized["valid"] = False
        normalized["source_unavailable"] = False
        return normalized

    def _missing_market_entry(self, *, is_yield: bool = False) -> dict:
        return {
            "price": None,
            "day_chg": None,
            "week_chg": None,
            "formatted": "DATA UNAVAILABLE",
            "is_yield": is_yield,
            "source": "unavailable",
            "source_label": "DATA UNAVAILABLE",
            "timestamp": "",
            "valid": False,
            "source_unavailable": True,
        }
