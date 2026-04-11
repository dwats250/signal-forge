"""
Layer 6 — Structure Engine

Classifies per-ticker market structure using derived metrics.
Runs only on symbols that passed validation and have sufficient OHLCV history.

Classifications: TREND | PULLBACK | BREAKOUT | REVERSAL | CHOP
CHOP → automatic disqualification (logged, never output).

IV environment is classified from VIX level and informs strategy preference.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from signal_forge.derived import DerivedMetrics
from signal_forge.normalization import NormalizedQuote

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Classification constants
# ---------------------------------------------------------------------------

STRUCT_TREND    = "TREND"
STRUCT_PULLBACK = "PULLBACK"
STRUCT_BREAKOUT = "BREAKOUT"
STRUCT_REVERSAL = "REVERSAL"
STRUCT_CHOP     = "CHOP"

IV_LOW      = "LOW_IV"
IV_NORMAL   = "NORMAL_IV"
IV_ELEVATED = "ELEVATED_IV"
IV_HIGH     = "HIGH_IV"

STRAT_DEBIT         = "debit"
STRAT_CREDIT        = "credit"
STRAT_EITHER        = "either"
STRAT_DEFINED_RISK  = "defined_risk_reduced"

# Thresholds from PRD
_BREAKOUT_MOMENTUM_MIN  = 0.02
_BREAKOUT_VOLUME_MIN    = 1.3
_CHOP_MOMENTUM_MAX      = 0.005   # abs(momentum_5d) < 0.005 → flat


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StructureReading:
    symbol: str
    classification: str              # TREND | PULLBACK | BREAKOUT | REVERSAL | CHOP
    ema_alignment: str               # "bull" | "bear" | "none"
    price_vs_ema21: str              # "above" | "below"
    price_vs_ema50: str              # "above" | "below"
    relative_strength: Optional[float]   # pct_change vs SPY pct_change (excess return)
    iv_environment: str              # LOW_IV | NORMAL_IV | ELEVATED_IV | HIGH_IV
    strategy_preference: str         # "debit" | "credit" | "either" | "defined_risk_reduced"
    disqualified: bool               # True when classification == CHOP
    computed_at_utc: datetime


# ---------------------------------------------------------------------------
# IV environment
# ---------------------------------------------------------------------------

def _classify_iv(vix_level: float) -> tuple[str, str]:
    """Return (iv_environment, strategy_preference) for a given VIX level."""
    if vix_level < 15:
        return IV_LOW, STRAT_DEBIT
    if vix_level <= 20:
        return IV_NORMAL, STRAT_EITHER
    if vix_level <= 28:
        return IV_ELEVATED, STRAT_CREDIT
    return IV_HIGH, STRAT_DEFINED_RISK


# ---------------------------------------------------------------------------
# Structure classification rules
# ---------------------------------------------------------------------------

def _ema_alignment(m: DerivedMetrics) -> str:
    if m.ema_aligned_bull:
        return "bull"
    if m.ema_aligned_bear:
        return "bear"
    return "none"


def _price_vs_ema(price: float, ema: Optional[float]) -> str:
    if ema is None:
        return "unknown"
    return "above" if price >= ema else "below"


def _classify_structure(
    price: float,
    m: DerivedMetrics,
) -> str:
    """
    Apply PRD structure classification rules in priority order.

    CHOP: EMA not aligned AND momentum flat (abs < 0.005) AND no directional structure
    BREAKOUT: price clearing EMA cluster, momentum > 0.02, volume ratio > 1.3
    REVERSAL: EMA crossover signal — ema9/ema21 relationship recently flipped
               (approximated: spread_pct sign conflicts with prior trend expectation)
    PULLBACK: EMA aligned, price temporarily below EMA9 but holding EMA21
    TREND: EMA aligned bull/bear, price respecting EMAs, momentum confirmed
    """
    aligned = m.ema_aligned_bull or m.ema_aligned_bear
    momentum = m.momentum_5d or 0.0
    vol_ratio = m.volume_ratio or 0.0
    spread = m.ema_spread_pct or 0.0

    # CHOP — highest priority disqualifier
    if not aligned and abs(momentum) < _CHOP_MOMENTUM_MAX:
        return STRUCT_CHOP

    # BREAKOUT
    if abs(momentum) >= _BREAKOUT_MOMENTUM_MIN and vol_ratio >= _BREAKOUT_VOLUME_MIN:
        return STRUCT_BREAKOUT

    # REVERSAL — spread is narrow and momentum opposes alignment
    # A reversal is signaled when ema9/ema21 are nearly crossed (spread < 0.5%)
    # and price momentum moves against the current EMA stance.
    if m.ema21 is not None and abs(spread) < 0.005:
        bull_reversal = m.ema_aligned_bull and momentum < -0.005
        bear_reversal = m.ema_aligned_bear and momentum > 0.005
        if bull_reversal or bear_reversal:
            return STRUCT_REVERSAL

    # PULLBACK — EMAs aligned but price has dipped below ema9
    if aligned and m.ema9 is not None:
        if price < m.ema9:
            return STRUCT_PULLBACK

    # TREND — default when aligned and no other condition triggered
    if aligned:
        return STRUCT_TREND

    # Catch-all: not aligned + has some momentum → still CHOP at this stage
    return STRUCT_CHOP


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify(
    quote: NormalizedQuote,
    metrics: DerivedMetrics,
    spy_pct_change: Optional[float] = None,
    vix_level: float = 20.0,
) -> StructureReading:
    """
    Classify structure for one symbol.

    spy_pct_change is used to compute relative strength (excess return vs SPY).
    vix_level determines IV environment and strategy preference.
    """
    now_utc = datetime.now(tz=timezone.utc)

    if not metrics.sufficient_history:
        logger.info("STRUCTURE SKIP | %s | insufficient history", quote.symbol)
        return StructureReading(
            symbol=quote.symbol,
            classification=STRUCT_CHOP,
            ema_alignment="none",
            price_vs_ema21="unknown",
            price_vs_ema50="unknown",
            relative_strength=None,
            iv_environment=_classify_iv(vix_level)[0],
            strategy_preference=_classify_iv(vix_level)[1],
            disqualified=True,
            computed_at_utc=now_utc,
        )

    classification = _classify_structure(quote.price, metrics)
    alignment = _ema_alignment(metrics)
    iv_env, strat_pref = _classify_iv(vix_level)

    pve21 = _price_vs_ema(quote.price, metrics.ema21)
    pve50 = _price_vs_ema(quote.price, metrics.ema50)

    rel_strength: Optional[float] = None
    if spy_pct_change is not None:
        rel_strength = quote.pct_change_decimal - spy_pct_change

    disqualified = classification == STRUCT_CHOP

    if disqualified:
        logger.info("STRUCTURE CHOP (disqualified) | %s | alignment=%s | momentum=%.4f",
                    quote.symbol, alignment, metrics.momentum_5d or 0.0)
    else:
        logger.info("STRUCTURE | %s | %s | alignment=%s | IV=%s | strat=%s",
                    quote.symbol, classification, alignment, iv_env, strat_pref)

    return StructureReading(
        symbol=quote.symbol,
        classification=classification,
        ema_alignment=alignment,
        price_vs_ema21=pve21,
        price_vs_ema50=pve50,
        relative_strength=rel_strength,
        iv_environment=iv_env,
        strategy_preference=strat_pref,
        disqualified=disqualified,
        computed_at_utc=now_utc,
    )


def classify_all(
    quotes: dict[str, NormalizedQuote],
    metrics: dict[str, DerivedMetrics],
    spy_pct_change: Optional[float] = None,
    vix_level: float = 20.0,
) -> dict[str, StructureReading]:
    """
    Classify structure for all symbols.
    Only classifies symbols that have both a valid quote and derived metrics.
    """
    results: dict[str, StructureReading] = {}
    for symbol in quotes:
        if symbol not in metrics:
            continue
        results[symbol] = classify(
            quotes[symbol],
            metrics[symbol],
            spy_pct_change=spy_pct_change,
            vix_level=vix_level,
        )
    return results
