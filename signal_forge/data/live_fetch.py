from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

try:
    from signal_forge.config import FMP_API_KEY
except ImportError:
    FMP_API_KEY = None

from signal_forge.execution.models.core import utc_now
from signal_forge.data.providers import FMPProvider, StooqProvider

REQUIRED_TICKERS = ["SPY", "QQQ", "IWM", "DXY", "VIX", "US10Y", "GOLD", "OIL", "XLE"]
YIELD_TICKERS = {"US10Y"}
TICKER_GROUPS = {
    "equities": ["SPY", "QQQ", "IWM"],
    "volatility": ["VIX"],
    "fx": ["DXY"],
    "rates": ["US10Y"],
    "metals": ["GOLD"],
    "energy": ["OIL", "XLE"],
}
CRITICAL_GROUPS = {"equities", "volatility"}
CRITICAL_MINIMUMS = {"equities": 2, "volatility": 1}
PROVIDER_SYMBOLS = {
    "fmp": {
        "SPY": "SPY",
        "QQQ": "QQQ",
        "IWM": "IWM",
        "DXY": "UUP",
        "VIX": "VIXY",
        "US10Y": "TLT",
        "GOLD": "XAUUSD",
        "OIL": "USO",
        "XLE": "XLE",
    },
    "stooq": {
        "SPY": "spy.us",
        "QQQ": "qqq.us",
        "IWM": "iwm.us",
        "DXY": "uup.us",
        "VIX": "vixy.us",
        "US10Y": "tlt.us",
        "GOLD": "xauusd",
        "OIL": "uso.us",
        "XLE": "xle.us",
    },
}


class HistoryProvider(Protocol):
    @property
    def name(self) -> str: ...

    def fetch_histories(self, symbol_map: dict[str, str]) -> tuple[dict[str, list[float]], object]: ...


class LiveDataUnavailableError(RuntimeError):
    pass


@dataclass
class SnapshotFetchResult:
    snapshot: dict[str, dict[str, object]]
    diagnostics: list[dict[str, object]]
    missing_tickers: list[str]
    missing_groups: list[str]
    partial_groups: list[str]
    critical_missing_groups: list[str]
    sources: list[str]
    mode: str
    decision: str
    fatal: bool


def get_api_key():
    return os.getenv("FMP_API_KEY") or FMP_API_KEY


def debug_fetch() -> None:
    import requests

    api_key = get_api_key()

    print("ENV CHECK:", api_key)
    print("DEBUG - API KEY PRESENT:", bool(api_key))

    if not api_key:
        print("ERROR - Missing FMP_API_KEY")
        return

    url = f"https://financialmodelingprep.com/api/v3/quote/SPY?apikey={api_key}"

    try:
        r = requests.get(url, timeout=5)
        print("DEBUG - STATUS CODE:", r.status_code)

        if r.status_code != 200:
            print("ERROR - Bad response:", r.text[:200])
            return

        data = r.json()

        if not data:
            print("ERROR - Empty response")
            return

        print("SUCCESS - SAMPLE DATA:", data[0])
    except Exception as e:
        print("ERROR - Exception:", str(e))


def fetch_market_snapshot(providers: list[HistoryProvider] | None = None) -> dict[str, dict[str, object]]:
    result = collect_market_snapshot(providers=providers)
    if result.fatal:
        summary = ", ".join(result.critical_missing_groups) or "minimum live dataset unavailable"
        raise LiveDataUnavailableError(summary)
    return result.snapshot


def collect_market_snapshot(providers: list[HistoryProvider] | None = None) -> SnapshotFetchResult:
    providers = providers or [FMPProvider(), StooqProvider()]
    snapshot = {ticker: _missing_entry(ticker) for ticker in REQUIRED_TICKERS}
    pending = set(REQUIRED_TICKERS)
    sources: list[str] = []
    diagnostics: list[dict[str, object]] = []

    for provider in providers[:2]:
        requested = sorted(pending)
        symbol_map = {
            ticker: PROVIDER_SYMBOLS.get(provider.name, {}).get(ticker, ticker)
            for ticker in pending
        }
        histories, provider_details = provider.fetch_histories(symbol_map)
        provider_diagnostics = _normalize_provider_diagnostics(provider.name, requested, provider_details)

        if histories:
            sources.append(provider.name)
        for ticker, closes in histories.items():
            if len(closes) < 2:
                continue
            snapshot[ticker] = _build_entry(ticker, closes, provider.name)
            pending.discard(ticker)

        diagnostics.extend(_summarize_provider_groups(provider.name, requested, histories, provider_diagnostics))
        if not pending:
            break

    missing_tickers = sorted(pending)
    missing_groups, partial_groups, critical_missing_groups = _classify_group_health(snapshot)
    fatal = bool(critical_missing_groups)
    mode = "unavailable" if fatal else "degraded" if missing_tickers else "full"
    decision = "skip" if fatal else "proceed"

    snapshot["_meta"] = {
        "fetched_at": utc_now(),
        "sources": sources or ["unavailable"],
        "missing_tickers": missing_tickers,
        "missing_groups": missing_groups,
        "partial_groups": partial_groups,
        "critical_missing_groups": critical_missing_groups,
        "mode": mode,
        "decision": decision,
        "diagnostics": diagnostics,
    }
    return SnapshotFetchResult(
        snapshot=snapshot,
        diagnostics=diagnostics,
        missing_tickers=missing_tickers,
        missing_groups=missing_groups,
        partial_groups=partial_groups,
        critical_missing_groups=critical_missing_groups,
        sources=sources or ["unavailable"],
        mode=mode,
        decision=decision,
        fatal=fatal,
    )


def build_live_context(snapshot: dict[str, dict[str, object]]) -> dict[str, object]:
    avg_equity = _average_change(snapshot, ["SPY", "QQQ", "IWM"])
    vix_change = _change(snapshot, "VIX")
    dxy_change = _change(snapshot, "DXY")
    oil_change = _change(snapshot, "OIL")
    gold_change = _change(snapshot, "GOLD")
    xle_change = _change(snapshot, "XLE")
    breadth_up = sum(1 for ticker in ["SPY", "QQQ", "IWM"] if (_change(snapshot, ticker) or 0.0) > 0)
    breadth_down = sum(1 for ticker in ["SPY", "QQQ", "IWM"] if (_change(snapshot, ticker) or 0.0) < 0)
    shock = (oil_change or 0.0) >= 4.0 and (gold_change or 0.0) >= 1.5
    iv_state = "expanding" if (vix_change or 0.0) >= 3.0 else "compressed" if (vix_change or 0.0) < 0 else "normal"

    context = {
        "market_snapshot": snapshot,
        "macro": _macro_block(avg_equity, dxy_change, vix_change),
        "geo": {
            "state": "bearish" if shock else "neutral",
            "confidence": "high" if shock else "medium",
            "key_factors": ["commodity stress rising"] if shock else ["geopolitical premium contained"],
            "special_flags": {"event_shock": shock},
        },
        "market_quality": _market_quality_block(breadth_up, breadth_down, vix_change),
        "options": {
            "state": "bearish" if (vix_change or 0.0) >= 3.0 else "bullish" if (vix_change or 0.0) < 0 else "neutral",
            "confidence": "high" if abs(vix_change or 0.0) >= 5.0 else "medium",
            "key_factors": [f"volatility {iv_state}"],
            "special_flags": {"iv_state": iv_state},
        },
        "dislocation": {("CL", "XLE"): (oil_change or 0.0, xle_change or 0.0)},
        "backtest_prices": _build_backtest_prices(avg_equity if avg_equity is not None else xle_change),
    }
    return context


def _macro_block(avg_equity: float | None, dxy_change: float | None, vix_change: float | None) -> dict[str, object]:
    bearish = (avg_equity is not None and avg_equity <= -0.35) or ((vix_change or 0.0) >= 3.0 and (dxy_change or 0.0) > 0)
    bullish = avg_equity is not None and avg_equity >= 0.35 and (vix_change is None or vix_change < 3.0)
    state = "bearish" if bearish else "bullish" if bullish else "neutral"
    return {
        "state": state,
        "confidence": "high" if avg_equity is not None and abs(avg_equity) >= 1.0 else "medium",
        "key_factors": [
            f"equity breadth avg {avg_equity:.2f}%" if avg_equity is not None else "equity breadth unavailable",
            f"dollar move {(dxy_change or 0.0):.2f}%",
            f"volatility move {(vix_change or 0.0):.2f}%",
        ],
    }


def _market_quality_block(breadth_up: int, breadth_down: int, vix_change: float | None) -> dict[str, object]:
    if breadth_up >= 2 and (vix_change is None or vix_change < 3.0):
        state = "bullish"
    elif breadth_down >= 2 or (vix_change or 0.0) >= 3.0:
        state = "bearish"
    else:
        state = "neutral"
    return {
        "state": state,
        "confidence": "high" if max(breadth_up, breadth_down) == 3 else "medium",
        "key_factors": [
            f"breadth_up {breadth_up}",
            f"breadth_down {breadth_down}",
            f"vix move {(vix_change or 0.0):.2f}%",
        ],
    }


def _build_backtest_prices(change: float | None) -> list[float]:
    base = 100.0
    drift = max(-0.03, min(0.03, (change or 0.0) / 100))
    return [round(base * (1 + drift * step / 5), 4) for step in range(6)]


def _build_entry(ticker: str, closes: list[float], source: str) -> dict[str, object]:
    current = float(closes[-1])
    prev = float(closes[-2])
    week_ago = float(closes[-6]) if len(closes) >= 6 else float(closes[0])
    if ticker in YIELD_TICKERS:
        day_chg = round((current - prev) * 100, 2)
        week_chg = round((current - week_ago) * 100, 2)
    else:
        day_chg = round((current - prev) / prev * 100, 2)
        week_chg = round((current - week_ago) / week_ago * 100, 2)
    return {
        "price": current,
        "day_chg": day_chg,
        "week_chg": week_chg,
        "source": source,
        "source_unavailable": False,
    }


def _missing_entry(ticker: str) -> dict[str, object]:
    return {
        "price": None,
        "day_chg": None,
        "week_chg": None,
        "source": None,
        "source_unavailable": True,
        "is_yield": ticker in YIELD_TICKERS,
    }


def _change(snapshot: dict[str, dict[str, object]], ticker: str) -> float | None:
    entry = snapshot.get(ticker, {})
    value = entry.get("day_chg")
    return float(value) if isinstance(value, (int, float)) else None


def _average_change(snapshot: dict[str, dict[str, object]], tickers: list[str]) -> float | None:
    values = [_change(snapshot, ticker) for ticker in tickers]
    present = [value for value in values if value is not None]
    if not present:
        return None
    return round(sum(present) / len(present), 2)


def _normalize_provider_diagnostics(
    provider_name: str,
    requested: list[str],
    provider_details: object,
) -> list[dict[str, object]]:
    if provider_details is None:
        return []
    if isinstance(provider_details, str):
        return [
            {
                "provider": provider_name,
                "symbol": symbol,
                "status": "failed",
                "error_type": "ProviderError",
                "error": provider_details,
            }
            for symbol in requested
        ]
    if isinstance(provider_details, list):
        normalized: list[dict[str, object]] = []
        for item in provider_details:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "provider": item.get("provider", provider_name),
                    "symbol": item.get("symbol"),
                    "status": item.get("status", "failed"),
                    "error_type": item.get("error_type"),
                    "error": item.get("error"),
                    "count": item.get("count"),
                }
            )
        return normalized
    return [
        {
            "provider": provider_name,
            "symbol": symbol,
            "status": "failed",
            "error_type": "ProviderError",
            "error": str(provider_details),
        }
        for symbol in requested
    ]


def _summarize_provider_groups(
    provider_name: str,
    requested: list[str],
    histories: dict[str, list[float]],
    provider_diagnostics: list[dict[str, object]],
) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    diag_by_symbol = {
        item.get("symbol"): item for item in provider_diagnostics if isinstance(item.get("symbol"), str)
    }
    for group, group_tickers in TICKER_GROUPS.items():
        requested_group = [ticker for ticker in group_tickers if ticker in requested]
        if not requested_group:
            continue
        success_symbols = [ticker for ticker in requested_group if ticker in histories]
        failure_items = [
            diag_by_symbol.get(ticker)
            for ticker in requested_group
            if ticker not in success_symbols and diag_by_symbol.get(ticker)
        ]
        status = "ok" if len(success_symbols) == len(requested_group) else "partial" if success_symbols else "failed"
        summary: dict[str, object] = {
            "provider": provider_name,
            "group": group,
            "status": status,
            "count": len(success_symbols),
            "symbols": requested_group,
        }
        if failure_items:
            first = failure_items[0]
            summary["error_type"] = first.get("error_type")
            summary["error"] = first.get("error")
        summaries.append(summary)
    return summaries


def _classify_group_health(
    snapshot: dict[str, dict[str, object]]
) -> tuple[list[str], list[str], list[str]]:
    missing_groups: list[str] = []
    partial_groups: list[str] = []
    critical_missing_groups: list[str] = []
    for group, tickers in TICKER_GROUPS.items():
        available = sum(1 for ticker in tickers if _change(snapshot, ticker) is not None)
        required = CRITICAL_MINIMUMS.get(group, len(tickers))
        if available == 0:
            missing_groups.append(group)
        elif available < len(tickers):
            partial_groups.append(group)
        if group in CRITICAL_GROUPS and available < required:
            critical_missing_groups.append(group)
    return missing_groups, partial_groups, critical_missing_groups
