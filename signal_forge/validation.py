"""
Layer 3 — Validation Gate

Hard pass/fail checks on NormalizedQuote.
No silent fallbacks. Every field must pass every check.

A failure on any HALT_SYMBOL aborts the entire pipeline.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from signal_forge.normalization import NormalizedQuote

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# If any of these fail validation the entire pipeline must halt.
HALT_SYMBOLS = {"^VIX", "DX-Y.NYB", "^TNX", "SPY", "QQQ"}

# Per-symbol price sanity bounds (inclusive).
PRICE_BOUNDS: dict[str, tuple[float, float]] = {
    "SPY":      (300,   900),
    "QQQ":      (200,   900),
    "IWM":      (100,   450),
    "GLD":      (100,   600),
    "SLV":      (10,    120),
    "GDX":      (15,    200),
    "PAAS":     (5,     120),
    "USO":      (40,    250),
    "XLE":      (50,    180),
    "NVDA":     (50,    2000),
    "TSLA":     (100,   600),
    "AAPL":     (120,   400),
    "META":     (200,   1000),
    "AMZN":     (100,   400),
    "COIN":     (50,    600),
    "MSTR":     (100,   2000),
    "^VIX":     (9,     90),
    "^TNX":     (1.0,   8.0),
    "DX-Y.NYB": (85,    125),
    "BTC-USD":  (10000, 200000),
}

_MAX_AGE_SECONDS = 300          # 5 minutes — premarket freshness threshold
_MAX_TIMESTAMP_AGE_SECONDS = 900  # 15 minutes — absolute timestamp gate
_MAX_PCT_CHANGE = 0.25


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ValidationResult:
    symbol: str
    passed: bool
    quote: Optional[NormalizedQuote]
    failure_reason: Optional[str]
    checks_run: list[str]
    checks_failed: list[str]


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_null_nan(q: NormalizedQuote) -> Optional[str]:
    """No field may be null or NaN for required numeric fields."""
    if math.isnan(q.price):
        return "price is NaN"
    if math.isnan(q.pct_change_decimal):
        return "pct_change_decimal is NaN"
    return None


def _check_types(q: NormalizedQuote) -> Optional[str]:
    if not isinstance(q.price, float):
        return f"price is not float: {type(q.price)}"
    if not isinstance(q.pct_change_decimal, float):
        return f"pct_change_decimal is not float: {type(q.pct_change_decimal)}"
    return None


def _check_freshness(q: NormalizedQuote) -> Optional[str]:
    if q.age_seconds >= _MAX_AGE_SECONDS:
        return f"age {q.age_seconds:.0f}s exceeds {_MAX_AGE_SECONDS}s threshold"
    return None


def _check_price_bounds(q: NormalizedQuote) -> Optional[str]:
    bounds = PRICE_BOUNDS.get(q.symbol)
    if bounds is None:
        return None  # no bounds defined — skip this check
    lo, hi = bounds
    if not (lo <= q.price <= hi):
        return f"price {q.price:.4f} outside bounds [{lo}, {hi}]"
    return None


def _check_pct_change(q: NormalizedQuote) -> Optional[str]:
    if abs(q.pct_change_decimal) >= _MAX_PCT_CHANGE:
        return f"pct_change {q.pct_change_decimal:.4f} exceeds ±{_MAX_PCT_CHANGE} — suspect data"
    return None


def _check_timestamp(q: NormalizedQuote) -> Optional[str]:
    now_utc = datetime.now(tz=timezone.utc)
    ts_age = (now_utc - q.fetched_at_utc).total_seconds()
    if ts_age > _MAX_TIMESTAMP_AGE_SECONDS:
        return f"fetched_at_utc is {ts_age:.0f}s old (> {_MAX_TIMESTAMP_AGE_SECONDS}s)"
    return None


# ---------------------------------------------------------------------------
# Full validation for one symbol
# ---------------------------------------------------------------------------

_CHECKS = [
    ("null_nan",   _check_null_nan),
    ("types",      _check_types),
    ("freshness",  _check_freshness),
    ("price_bounds", _check_price_bounds),
    ("pct_change", _check_pct_change),
    ("timestamp",  _check_timestamp),
]


def validate(q: NormalizedQuote) -> ValidationResult:
    """Run all checks against a NormalizedQuote. Returns a ValidationResult."""
    checks_run: list[str] = []
    checks_failed: list[str] = []
    failure_reason: Optional[str] = None

    for name, check_fn in _CHECKS:
        checks_run.append(name)
        reason = check_fn(q)
        if reason is not None:
            checks_failed.append(name)
            if failure_reason is None:
                failure_reason = reason
            # Continue running remaining checks for full auditability

    passed = len(checks_failed) == 0
    if not passed:
        logger.warning("VALIDATION FAIL | %s | %s | checks_failed=%s", q.symbol, failure_reason, checks_failed)
    else:
        logger.debug("VALIDATION PASS | %s", q.symbol)

    return ValidationResult(
        symbol=q.symbol,
        passed=passed,
        quote=q if passed else None,
        failure_reason=failure_reason,
        checks_run=checks_run,
        checks_failed=checks_failed,
    )


# ---------------------------------------------------------------------------
# Batch validation with halt detection
# ---------------------------------------------------------------------------

class PipelineHaltError(Exception):
    """Raised when a required macro symbol fails validation."""

    def __init__(self, symbol: str, reason: str) -> None:
        self.symbol = symbol
        self.reason = reason
        super().__init__(
            f"\n⚠  SYSTEM HALT — MACRO DATA INVALID\n"
            f"Failed symbol: {symbol} (reason: {reason})\n"
            f"DO NOT TRADE — DATA UNTRUSTWORTHY"
        )


def validate_all(quotes: dict[str, NormalizedQuote]) -> list[ValidationResult]:
    """
    Validate all quotes. Returns a list of ValidationResult (one per symbol).
    Raises PipelineHaltError immediately if any HALT_SYMBOL fails.
    Non-halt symbol failures are included in the list with passed=False.
    """
    results: list[ValidationResult] = []

    for symbol, quote in quotes.items():
        result = validate(quote)
        results.append(result)

        if not result.passed and symbol in HALT_SYMBOLS:
            raise PipelineHaltError(symbol=symbol, reason=result.failure_reason or "unknown")

    return results
