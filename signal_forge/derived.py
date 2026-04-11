"""
Layer 4 — Derived Metrics

Computes EMA, ATR, momentum, and volume metrics from OHLCV history.
Only operates on symbols that passed Layer 3 validation.
Requires minimum 21 bars — returns sufficient_history=False if unavailable.

OHLCV is loaded from the parquet cache at data/cache/{symbol}_ohlcv.parquet.
Cache refresh (fetch + write) is handled by fetch_ohlcv().
"""

from __future__ import annotations

import logging
import math
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

from signal_forge.normalization import NormalizedQuote

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_CACHE_DIR = Path("data/cache")
_CACHE_STALE_HOURS = 12
# 6 months (~126 bars) — EMA21 needs ≥63 bars to converge; EMA50 needs ≥150
# 6mo is the minimum that gives EMA21 full accuracy and reasonable EMA50 accuracy
_OHLCV_PERIOD = "6mo"
_MIN_BARS_EMA = 21    # hard minimum to return sufficient_history=True
_MIN_BARS_ATR = 14
_MIN_BARS_VOLUME = 20
_MIN_BARS_MOMENTUM = 5


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DerivedMetrics:
    symbol: str
    ema9: Optional[float]
    ema21: Optional[float]
    ema50: Optional[float]
    ema_aligned_bull: bool           # ema9 > ema21 > ema50
    ema_aligned_bear: bool           # ema9 < ema21 < ema50
    ema_spread_pct: Optional[float]  # (ema9 - ema21) / ema21
    atr14: Optional[float]           # 14-period ATR in price units
    atr_pct: Optional[float]         # ATR as % of current price
    momentum_5d: Optional[float]     # 5-day return, decimal
    volume_ratio: Optional[float]    # today's vol / 20d avg vol
    iv_proxy: Optional[float]        # VIX level as IV proxy (None for non-equity)
    computed_at_utc: datetime
    sufficient_history: bool         # False if < 21 bars available


# ---------------------------------------------------------------------------
# Cache utilities
# ---------------------------------------------------------------------------

def _cache_path(symbol: str) -> Path:
    """Return parquet cache path for a symbol, sanitizing special characters."""
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", symbol)
    return _CACHE_DIR / f"{safe}_ohlcv.parquet"


def _cache_is_fresh(path: Path) -> bool:
    """Return True if the cache file exists and was written within the stale threshold."""
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age = datetime.now(tz=timezone.utc) - mtime
    return age < timedelta(hours=_CACHE_STALE_HOURS)


def _load_cache(path: Path) -> Optional[pd.DataFrame]:
    try:
        df = pd.read_parquet(path)
        return df
    except Exception as exc:
        logger.warning("Cache read failed for %s: %s", path, exc)
        return None


def _save_cache(path: Path, df: pd.DataFrame) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path)
    except Exception as exc:
        logger.warning("Cache write failed for %s: %s", path, exc)


def fetch_ohlcv(symbol: str) -> Optional[pd.DataFrame]:
    """
    Return OHLCV DataFrame (30 trading days) for symbol.
    Uses cache if fresh; fetches from yfinance otherwise.
    Returns None if fetch fails and no valid cache exists.
    """
    path = _cache_path(symbol)

    if _cache_is_fresh(path):
        df = _load_cache(path)
        if df is not None and len(df) >= _MIN_BARS_ATR:
            logger.debug("OHLCV cache hit: %s (%d bars)", symbol, len(df))
            return df

    logger.info("OHLCV fetch: %s", symbol)
    try:
        df = yf.download(symbol, period=_OHLCV_PERIOD, interval="1d", progress=False, auto_adjust=True)
        if df.empty:
            raise ValueError("yfinance returned empty DataFrame")

        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        _save_cache(path, df)
        logger.info("OHLCV fetch OK: %s (%d bars)", symbol, len(df))
        return df

    except Exception as exc:
        logger.error("OHLCV fetch FAILED for %s: %s", symbol, exc)

        # Return stale cache if available rather than nothing
        stale = _load_cache(path)
        if stale is not None:
            logger.warning("Using stale OHLCV cache for %s — symbol marked INVALID for derived metrics", symbol)
        return None  # stale cache still means INVALID per spec


# ---------------------------------------------------------------------------
# Indicator calculations
# ---------------------------------------------------------------------------

def _ema(series: pd.Series, span: int) -> float:
    """Compute EMA of the given span on a close price series."""
    result = series.ewm(span=span, adjust=False).mean()
    return float(result.iloc[-1])


def _atr14(df: pd.DataFrame) -> float:
    """
    Compute 14-period ATR using Wilder's smoothing (RMA).

    TradingView uses ta.rma(tr, 14) — NOT a simple rolling mean.
    Wilder's RMA: alpha = 1/period → ewm(alpha=1/14, adjust=False)
    This differs from standard EMA (alpha = 2/(period+1) = 2/15 ≈ 0.133).
    """
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    # Wilder's smoothing: alpha = 1/14, not 2/15
    atr = tr.ewm(alpha=1.0 / 14, adjust=False).mean()
    return float(atr.iloc[-1])


def _momentum_5d(close: pd.Series) -> float:
    """5-day return as decimal."""
    if len(close) < _MIN_BARS_MOMENTUM + 1:
        return float("nan")
    return float((close.iloc[-1] - close.iloc[-6]) / close.iloc[-6])


def _volume_ratio(df: pd.DataFrame) -> float:
    """Today's volume / 20-day average volume."""
    if len(df) < _MIN_BARS_VOLUME + 1:
        return float("nan")
    today_vol = float(df["Volume"].iloc[-1])
    avg_vol = float(df["Volume"].iloc[-_MIN_BARS_VOLUME - 1:-1].mean())
    if avg_vol == 0:
        return float("nan")
    return today_vol / avg_vol


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute(
    quote: NormalizedQuote,
    vix_level: Optional[float] = None,
) -> DerivedMetrics:
    """
    Compute derived metrics for one validated symbol.
    vix_level is passed through as iv_proxy for equity symbols.
    Returns a DerivedMetrics with sufficient_history=False if < 21 bars.
    """
    now_utc = datetime.now(tz=timezone.utc)
    df = fetch_ohlcv(quote.symbol)

    if df is None or len(df) < _MIN_BARS_EMA:
        logger.warning("Insufficient OHLCV for %s — derived metrics unavailable", quote.symbol)
        return DerivedMetrics(
            symbol=quote.symbol,
            ema9=None, ema21=None, ema50=None,
            ema_aligned_bull=False, ema_aligned_bear=False,
            ema_spread_pct=None,
            atr14=None, atr_pct=None,
            momentum_5d=None, volume_ratio=None,
            iv_proxy=vix_level,
            computed_at_utc=now_utc,
            sufficient_history=False,
        )

    close = df["Close"]
    ema9 = _ema(close, 9)
    ema21 = _ema(close, 21)
    # EMA50 requires 50+ bars; gracefully handle shorter history
    ema50: Optional[float] = _ema(close, 50) if len(close) >= 50 else None

    ema_aligned_bull = (
        ema50 is not None
        and ema9 > ema21 > ema50
        and not math.isnan(ema9)
        and not math.isnan(ema21)
    )
    ema_aligned_bear = (
        ema50 is not None
        and ema9 < ema21 < ema50
        and not math.isnan(ema9)
        and not math.isnan(ema21)
    )
    ema_spread_pct = (ema9 - ema21) / ema21 if ema21 != 0 else None

    atr = _atr14(df) if len(df) >= _MIN_BARS_ATR else None
    atr_pct = (atr / quote.price) if (atr is not None and quote.price > 0) else None

    mom5 = _momentum_5d(close)
    vol_ratio = _volume_ratio(df)

    # iv_proxy is only meaningful for equity symbols
    is_equity = quote.units == "usd_price" and not quote.symbol.startswith("^")
    iv = vix_level if is_equity else None

    return DerivedMetrics(
        symbol=quote.symbol,
        ema9=ema9,
        ema21=ema21,
        ema50=ema50,
        ema_aligned_bull=ema_aligned_bull,
        ema_aligned_bear=ema_aligned_bear,
        ema_spread_pct=ema_spread_pct,
        atr14=atr,
        atr_pct=atr_pct,
        momentum_5d=mom5 if not math.isnan(mom5) else None,
        volume_ratio=vol_ratio if not math.isnan(vol_ratio) else None,
        iv_proxy=iv,
        computed_at_utc=now_utc,
        sufficient_history=True,
    )


def compute_all(
    validated_quotes: dict[str, NormalizedQuote],
    vix_level: Optional[float] = None,
) -> dict[str, DerivedMetrics]:
    """Compute derived metrics for all validated symbols."""
    return {
        symbol: compute(quote, vix_level=vix_level)
        for symbol, quote in validated_quotes.items()
    }


# ---------------------------------------------------------------------------
# Gate check — compare SPY metrics against TradingView reference values
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GateCheckResult:
    passed: bool
    ema9: float
    ema21: float
    atr14: float
    bar_count: int
    last_date: str
    failures: list[str]


def gate_check_spy(
    tv_ema9: Optional[float] = None,
    tv_ema21: Optional[float] = None,
    tv_atr14: Optional[float] = None,
    ema_tol: float = 0.001,    # 0.1%
    atr_tol: float = 0.05,     # 5%
) -> GateCheckResult:
    """
    Fetch SPY OHLCV, compute EMA9/EMA21/ATR14, and compare to TradingView values.

    TradingView settings to match:
      - Symbol: SPY, Timeframe: 1D
      - EMA(9) close, EMA(21) close  [default EMA settings]
      - ATR(14)  [default ATR — uses RMA/Wilder's, not SMA]

    Tolerance:
      - EMAs: within 0.1% of TV value
      - ATR14: within 5% of TV value

    Pass tv_ema9 / tv_ema21 / tv_atr14 to run comparison.
    Omit them to just print computed values for manual inspection.
    """
    df = fetch_ohlcv("SPY")
    if df is None or len(df) < _MIN_BARS_EMA:
        raise RuntimeError("SPY OHLCV unavailable — cannot run gate check")

    close = df["Close"]
    ema9  = _ema(close, 9)
    ema21 = _ema(close, 21)
    atr   = _atr14(df)
    bars  = len(df)
    last_date = str(df.index[-1].date()) if hasattr(df.index[-1], "date") else str(df.index[-1])

    print("\n── SPY Derived Metrics Gate Check ─────────────────────────")
    print(f"  Bars loaded  : {bars} (period={_OHLCV_PERIOD})")
    print(f"  Last bar     : {last_date}")
    print(f"  EMA9         : {ema9:.4f}")
    print(f"  EMA21        : {ema21:.4f}")
    print(f"  ATR14        : {atr:.4f}")

    failures: list[str] = []

    if tv_ema9 is not None:
        diff = abs(ema9 - tv_ema9) / tv_ema9
        status = "PASS" if diff <= ema_tol else "FAIL"
        print(f"\n  EMA9  vs TV  : {ema9:.4f} vs {tv_ema9:.4f}  ({diff*100:.3f}%)  [{status}]")
        if diff > ema_tol:
            failures.append(f"EMA9 diff {diff*100:.3f}% > {ema_tol*100:.1f}% tolerance")

    if tv_ema21 is not None:
        diff = abs(ema21 - tv_ema21) / tv_ema21
        status = "PASS" if diff <= ema_tol else "FAIL"
        print(f"  EMA21 vs TV  : {ema21:.4f} vs {tv_ema21:.4f}  ({diff*100:.3f}%)  [{status}]")
        if diff > ema_tol:
            failures.append(f"EMA21 diff {diff*100:.3f}% > {ema_tol*100:.1f}% tolerance")

    if tv_atr14 is not None:
        diff = abs(atr - tv_atr14) / tv_atr14
        status = "PASS" if diff <= atr_tol else "FAIL"
        print(f"  ATR14 vs TV  : {atr:.4f} vs {tv_atr14:.4f}  ({diff*100:.2f}%)  [{status}]")
        if diff > atr_tol:
            failures.append(f"ATR14 diff {diff*100:.2f}% > {atr_tol*100:.1f}% tolerance")

    has_comparisons = any(v is not None for v in [tv_ema9, tv_ema21, tv_atr14])
    passed = len(failures) == 0 if has_comparisons else True

    if has_comparisons:
        verdict = "GATE PASS ✓" if passed else f"GATE FAIL ✗  ({len(failures)} failure(s))"
        print(f"\n  Result       : {verdict}")

    print("────────────────────────────────────────────────────────────\n")
    return GateCheckResult(
        passed=passed,
        ema9=ema9,
        ema21=ema21,
        atr14=atr,
        bar_count=bars,
        last_date=last_date,
        failures=failures,
    )
