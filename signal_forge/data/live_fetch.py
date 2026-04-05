from __future__ import annotations

from typing import Protocol

from signal_forge.execution.models.core import utc_now
from signal_forge.data.providers import FMPProvider, StooqProvider

REQUIRED_TICKERS = ["SPY", "QQQ", "IWM", "DXY", "VIX", "US10Y", "GOLD", "OIL", "XLE"]
YIELD_TICKERS = {"US10Y"}
PROVIDER_SYMBOLS = {
    "fmp": {
        "SPY": "SPY",
        "QQQ": "QQQ",
        "IWM": "IWM",
        "DXY": "UUP",
        "VIX": "VIXY",
        "US10Y": "TLT",
        "GOLD": "GLD",
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
        "GOLD": "gld.us",
        "OIL": "uso.us",
        "XLE": "xle.us",
    },
}


class HistoryProvider(Protocol):
    @property
    def name(self) -> str: ...

    def fetch_histories(self, symbol_map: dict[str, str]) -> tuple[dict[str, list[float]], str | None]: ...


class LiveDataUnavailableError(RuntimeError):
    pass


def fetch_market_snapshot(providers: list[HistoryProvider] | None = None) -> dict[str, dict[str, object]]:
    providers = providers or [FMPProvider(), StooqProvider()]
    snapshot = {ticker: _missing_entry(ticker) for ticker in REQUIRED_TICKERS}
    pending = set(REQUIRED_TICKERS)
    sources: list[str] = []
    errors: list[str] = []

    for provider in providers[:2]:
        symbol_map = {
            ticker: PROVIDER_SYMBOLS.get(provider.name, {}).get(ticker, ticker)
            for ticker in pending
        }
        histories, reason = provider.fetch_histories(symbol_map)
        if reason:
            errors.append(f"{provider.name}: {reason}")
        if not histories:
            continue

        sources.append(provider.name)
        for ticker, closes in histories.items():
            if len(closes) < 2:
                continue
            snapshot[ticker] = _build_entry(ticker, closes, provider.name)
            pending.discard(ticker)
        if not pending:
            break

    if pending:
        raise LiveDataUnavailableError("; ".join(errors) or "live data unavailable")

    snapshot["_meta"] = {
        "fetched_at": utc_now(),
        "sources": sources or ["unavailable"],
        "errors": errors,
        "missing_tickers": sorted(pending),
    }
    return snapshot


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
