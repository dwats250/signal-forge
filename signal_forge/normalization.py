"""
Layer 2 — Normalization

Converts RawQuote → NormalizedQuote:
  - pct_change always in decimal form (0.052, not 5.2)
  - units annotated per symbol
  - timestamps always UTC with tzinfo
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from signal_forge.ingestion import RawQuote

# ---------------------------------------------------------------------------
# Unit classification per symbol
# ---------------------------------------------------------------------------

_UNIT_MAP: dict[str, str] = {
    "^VIX":     "index_level",
    "DX-Y.NYB": "index_level",
    "^TNX":     "yield_pct",    # stored as e.g. 4.31 — not converted, documented
    "BTC-USD":  "usd_price",
}

_DEFAULT_UNIT = "usd_price"


def _classify_units(symbol: str) -> str:
    return _UNIT_MAP.get(symbol, _DEFAULT_UNIT)


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NormalizedQuote:
    symbol: str
    price: float
    pct_change_decimal: float    # ALWAYS decimal: 5.2% → 0.052
    volume: Optional[float]
    fetched_at_utc: datetime     # UTC, always timezone-aware
    source: str
    units: str                   # "usd_price" | "index_level" | "yield_pct"
    age_seconds: float           # seconds since fetched_at_utc at normalization time


# ---------------------------------------------------------------------------
# Normalization logic
# ---------------------------------------------------------------------------

def _ensure_utc(dt: datetime) -> datetime:
    """Guarantee a datetime has UTC tzinfo attached."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_decimal(pct_raw: float) -> float:
    """
    Normalize pct_change to decimal form.
    yfinance fast_info already returns decimal (0.052 not 5.2), so no division.
    Polygon open→close computation also yields decimal.
    This function is a passthrough + guard against obviously wrong values
    (e.g. if a source returned 5.2 instead of 0.052).
    """
    # Heuristic: if abs(pct_raw) > 1.0, it was likely provided as a percentage
    if abs(pct_raw) > 1.0:
        return pct_raw / 100.0
    return pct_raw


def normalize(raw: RawQuote) -> NormalizedQuote:
    """
    Convert a RawQuote to NormalizedQuote.
    Called even for failed quotes so the pipeline always has a consistent type
    (the validation layer will catch and reject the NaN values).
    """
    fetched_at = _ensure_utc(raw.fetched_at_utc)
    now_utc = datetime.now(tz=timezone.utc)
    age_seconds = (now_utc - fetched_at).total_seconds()

    return NormalizedQuote(
        symbol=raw.symbol,
        price=raw.price,
        pct_change_decimal=_to_decimal(raw.pct_change_raw),
        volume=raw.volume,
        fetched_at_utc=fetched_at,
        source=raw.source,
        units=_classify_units(raw.symbol),
        age_seconds=age_seconds,
    )


def normalize_all(raw_quotes: dict[str, RawQuote]) -> dict[str, NormalizedQuote]:
    """Normalize a batch of raw quotes. Always returns the full dict."""
    return {symbol: normalize(q) for symbol, q in raw_quotes.items()}
