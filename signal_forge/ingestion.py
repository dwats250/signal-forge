"""
Layer 1 — Raw Ingestion

Fetches raw quotes from yfinance (primary) and Polygon.io (fallback).
No transforms, no math — raw values only.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests
import yfinance as yf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source priority — yfinance-only symbols cannot fall back to Polygon
# ---------------------------------------------------------------------------

YFINANCE_ONLY = {"^VIX", "DX-Y.NYB", "^TNX", "BTC-USD"}

SYMBOL_SOURCE_PRIORITY: dict[str, list[str]] = {
    "^VIX":     ["yfinance"],
    "DX-Y.NYB": ["yfinance"],
    "^TNX":     ["yfinance"],
    "BTC-USD":  ["yfinance"],
    "default":  ["yfinance", "polygon"],
}

# Full instrument universe per PRD
UNIVERSE: list[str] = [
    # Macro drivers (required)
    "^VIX", "DX-Y.NYB", "^TNX", "BTC-USD",
    # Indices (required)
    "SPY", "QQQ", "IWM",
    # Commodities
    "GLD", "SLV", "GDX", "PAAS", "USO", "XLE",
    # High-beta options vehicles
    "NVDA", "TSLA", "AAPL", "META", "AMZN", "COIN", "MSTR",
]


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RawQuote:
    symbol: str
    price: float
    pct_change_raw: float        # as-received — unit unknown until Layer 2
    volume: Optional[float]
    fetched_at_utc: datetime
    source: str                  # "yfinance" | "polygon"
    fetch_succeeded: bool
    failure_reason: Optional[str]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_RETRY_ATTEMPTS = 3
_RETRY_BACKOFF_S = 2
_TIMEOUT_S = 10


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _fetch_yfinance(symbol: str) -> RawQuote:
    """Attempt to fetch a quote from yfinance. Returns a failed RawQuote on error."""
    start = time.monotonic()
    last_exc: Optional[Exception] = None

    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            ticker = yf.Ticker(symbol)
            fi = ticker.fast_info

            price = fi.last_price
            prev_close = fi.previous_close

            if price is None or prev_close is None:
                raise ValueError(f"fast_info returned None: price={price}, prev_close={prev_close}")

            pct_change_raw = (price - prev_close) / prev_close
            volume = getattr(fi, "three_month_average_volume", None) or getattr(fi, "regular_market_volume", None)

            elapsed = time.monotonic() - start
            logger.info(
                "yfinance fetch OK | %s | price=%.4f | pct=%.4f | attempt=%d | %.2fs",
                symbol, price, pct_change_raw, attempt, elapsed,
            )
            return RawQuote(
                symbol=symbol,
                price=float(price),
                pct_change_raw=float(pct_change_raw),
                volume=float(volume) if volume is not None else None,
                fetched_at_utc=_now_utc(),
                source="yfinance",
                fetch_succeeded=True,
                failure_reason=None,
            )

        except Exception as exc:
            last_exc = exc
            logger.warning("yfinance attempt %d/%d failed for %s: %s", attempt, _RETRY_ATTEMPTS, symbol, exc)
            if attempt < _RETRY_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF_S)

    elapsed = time.monotonic() - start
    logger.error("yfinance FAILED for %s after %d attempts (%.2fs): %s", symbol, _RETRY_ATTEMPTS, elapsed, last_exc)
    return RawQuote(
        symbol=symbol,
        price=float("nan"),
        pct_change_raw=float("nan"),
        volume=None,
        fetched_at_utc=_now_utc(),
        source="yfinance",
        fetch_succeeded=False,
        failure_reason=str(last_exc),
    )


def _polygon_symbol(symbol: str) -> str:
    """Map yfinance-style ticker to Polygon ticker (equities only)."""
    return symbol.upper()


def _fetch_polygon(symbol: str) -> RawQuote:
    """Attempt to fetch previous-day data from Polygon free tier."""
    api_key = os.environ.get("POLYGON_API_KEY", "")
    if not api_key:
        return RawQuote(
            symbol=symbol,
            price=float("nan"),
            pct_change_raw=float("nan"),
            volume=None,
            fetched_at_utc=_now_utc(),
            source="polygon",
            fetch_succeeded=False,
            failure_reason="POLYGON_API_KEY not set",
        )

    poly_symbol = _polygon_symbol(symbol)
    url = f"https://api.polygon.io/v2/aggs/ticker/{poly_symbol}/prev"
    params = {"adjusted": "true", "apiKey": api_key}
    start = time.monotonic()
    last_exc: Optional[Exception] = None

    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            resp = requests.get(url, params=params, timeout=_TIMEOUT_S)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            if not results:
                raise ValueError(f"Polygon returned empty results for {poly_symbol}")

            bar = results[0]
            close = float(bar["c"])
            open_ = float(bar["o"])
            volume = float(bar.get("v", 0)) or None
            pct_change_raw = (close - open_) / open_

            elapsed = time.monotonic() - start
            logger.info(
                "polygon fetch OK | %s | price=%.4f | pct=%.4f | attempt=%d | %.2fs (15min delay)",
                symbol, close, pct_change_raw, attempt, elapsed,
            )
            return RawQuote(
                symbol=symbol,
                price=close,
                pct_change_raw=pct_change_raw,
                volume=volume,
                fetched_at_utc=_now_utc(),
                source="polygon",
                fetch_succeeded=True,
                failure_reason=None,
            )

        except Exception as exc:
            last_exc = exc
            logger.warning("polygon attempt %d/%d failed for %s: %s", attempt, _RETRY_ATTEMPTS, symbol, exc)
            if attempt < _RETRY_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF_S)

    elapsed = time.monotonic() - start
    logger.error("polygon FAILED for %s after %d attempts (%.2fs): %s", symbol, _RETRY_ATTEMPTS, elapsed, last_exc)
    return RawQuote(
        symbol=symbol,
        price=float("nan"),
        pct_change_raw=float("nan"),
        volume=None,
        fetched_at_utc=_now_utc(),
        source="polygon",
        fetch_succeeded=False,
        failure_reason=str(last_exc),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_quote(symbol: str) -> RawQuote:
    """
    Fetch a raw quote for one symbol using the configured source priority.
    yfinance-only symbols never fall back to Polygon.
    Always returns a RawQuote — succeeded or failed, never raises.
    """
    sources = SYMBOL_SOURCE_PRIORITY.get(symbol, SYMBOL_SOURCE_PRIORITY["default"])

    for source in sources:
        if source == "yfinance":
            quote = _fetch_yfinance(symbol)
        elif source == "polygon":
            quote = _fetch_polygon(symbol)
        else:
            continue

        if quote.fetch_succeeded:
            return quote
        # Try next source

    # All sources failed — return the last failed quote (it has the failure_reason)
    return quote  # type: ignore[return-value]


def fetch_all(symbols: Optional[list[str]] = None) -> dict[str, RawQuote]:
    """
    Fetch quotes for all symbols independently.
    Defaults to the full UNIVERSE when no symbols list is provided.
    One symbol's failure never affects another.
    Returns a dict keyed by symbol.
    """
    if symbols is None:
        symbols = UNIVERSE
    results: dict[str, RawQuote] = {}
    for symbol in symbols:
        results[symbol] = fetch_quote(symbol)
    return results
