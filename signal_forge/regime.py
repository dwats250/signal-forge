"""
Layer 5 — Macro Regime Engine

Classifies the current market regime from validated macro + index quotes.
Uses a transparent vote-counting model (8 inputs, ±1 votes, no weights).

Regime states: RISK_ON | RISK_OFF | TRANSITION | CHAOTIC
Execution posture: maps regime + confidence to 5 postures.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from signal_forge.normalization import NormalizedQuote

if TYPE_CHECKING:
    from signal_forge.validation import ValidationResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regime + posture constants
# ---------------------------------------------------------------------------

REGIME_RISK_ON    = "RISK_ON"
REGIME_RISK_OFF   = "RISK_OFF"
REGIME_TRANSITION = "TRANSITION"
REGIME_CHAOTIC    = "CHAOTIC"

POSTURE_AGGRESSIVE_LONG  = "AGGRESSIVE_LONG"
POSTURE_CONTROLLED_LONG  = "CONTROLLED_LONG"
POSTURE_NEUTRAL_PREMIUM  = "NEUTRAL_PREMIUM"
POSTURE_DEFENSIVE_SHORT  = "DEFENSIVE_SHORT"
POSTURE_STAY_FLAT        = "STAY_FLAT"

_VIX_SPIKE_THRESHOLD = 0.15   # VIX pct_change > +15% → CHAOTIC override
_VIX_ELEVATED_LOW    = 18.0
_VIX_ELEVATED_HIGH   = 25.0


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegimeState:
    regime: str                      # RISK_ON | RISK_OFF | TRANSITION | CHAOTIC
    posture: str                      # one of the 5 POSTURE_ constants
    confidence: float                 # 0.0 – 1.0
    net_score: int                    # sum of all votes
    total_votes: int                  # number of inputs that cast a vote
    vote_breakdown: dict[str, int]    # symbol/key → vote, for full auditability
    vix_level: float
    vix_change: float
    tradeable: bool                   # False if STAY_FLAT or CHAOTIC
    computed_at_utc: datetime


# ---------------------------------------------------------------------------
# Vote-casting rules (per PRD scoring model)
# ---------------------------------------------------------------------------

def _vote_spy(q: NormalizedQuote) -> int:
    if q.pct_change_decimal > 0.003:
        return +1
    if q.pct_change_decimal < -0.003:
        return -1
    return 0


def _vote_qqq(q: NormalizedQuote) -> int:
    if q.pct_change_decimal > 0.003:
        return +1
    if q.pct_change_decimal < -0.003:
        return -1
    return 0


def _vote_iwm(q: NormalizedQuote) -> int:
    if q.pct_change_decimal > 0.004:
        return +1
    if q.pct_change_decimal < -0.004:
        return -1
    return 0


def _vote_vix_level(vix_level: float) -> int:
    if vix_level < 18:
        return +1
    if vix_level > 25:
        return -1
    return 0


def _vote_vix_change(vix_change: float) -> int:
    if vix_change < -0.03:
        return +1
    if vix_change > 0.05:
        return -1
    return 0


def _vote_dxy(q: NormalizedQuote) -> int:
    if q.pct_change_decimal < -0.002:
        return +1
    if q.pct_change_decimal > 0.003:
        return -1
    return 0


def _vote_tnx(q: NormalizedQuote) -> int:
    if q.pct_change_decimal < -0.005:
        return +1
    if q.pct_change_decimal > 0.008:
        return -1
    return 0


def _vote_btc(q: NormalizedQuote) -> int:
    if q.pct_change_decimal > 0.015:
        return +1
    if q.pct_change_decimal < -0.020:
        return -1
    return 0


# ---------------------------------------------------------------------------
# Regime classification logic
# ---------------------------------------------------------------------------

def _classify_regime(
    net_score: int,
    total_votes: int,
    confidence: float,
    vix_change: float,
    vix_level: float,
) -> str:
    """Apply PRD classification rules in priority order."""

    # VIX spike → CHAOTIC, overrides everything
    if vix_change > _VIX_SPIKE_THRESHOLD:
        return REGIME_CHAOTIC

    if net_score >= 4 and confidence >= 0.60:
        return REGIME_RISK_ON
    if net_score >= 2:
        return REGIME_RISK_ON

    if net_score <= -4 and confidence >= 0.60:
        return REGIME_RISK_OFF
    if net_score <= -2:
        return REGIME_RISK_OFF

    return REGIME_TRANSITION


def _classify_posture(regime: str, confidence: float, vix_level: float) -> str:
    """Map regime + confidence to execution posture."""
    if regime == REGIME_CHAOTIC:
        return POSTURE_STAY_FLAT
    if confidence < 0.50:
        return POSTURE_STAY_FLAT
    if regime == REGIME_TRANSITION:
        if vix_level > _VIX_ELEVATED_HIGH:
            return POSTURE_STAY_FLAT
        return POSTURE_NEUTRAL_PREMIUM
    if regime == REGIME_RISK_ON:
        if confidence >= 0.75:
            return POSTURE_AGGRESSIVE_LONG
        return POSTURE_CONTROLLED_LONG
    if regime == REGIME_RISK_OFF:
        if confidence >= 0.55:
            return POSTURE_DEFENSIVE_SHORT
        return POSTURE_STAY_FLAT
    return POSTURE_STAY_FLAT


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_regime(quotes: dict[str, NormalizedQuote]) -> RegimeState:
    """
    Run the macro regime engine against a dict of validated NormalizedQuotes.
    Missing symbols cast no vote (0) rather than halting — the vote count reflects
    only available data.

    Required inputs (from HALT_SYMBOLS): VIX, DXY, TNX, SPY, QQQ.
    Optional inputs: IWM, BTC-USD.
    """
    now_utc = datetime.now(tz=timezone.utc)
    vote_breakdown: dict[str, int] = {}
    total_votes = 0
    net_score = 0

    def _cast(key: str, vote: int) -> None:
        nonlocal net_score, total_votes
        vote_breakdown[key] = vote
        net_score += vote
        total_votes += 1

    # --- Required inputs ---
    if "SPY" in quotes:
        _cast("SPY", _vote_spy(quotes["SPY"]))
    if "QQQ" in quotes:
        _cast("QQQ", _vote_qqq(quotes["QQQ"]))
    if "DX-Y.NYB" in quotes:
        _cast("DXY", _vote_dxy(quotes["DX-Y.NYB"]))
    if "^TNX" in quotes:
        _cast("TNX", _vote_tnx(quotes["^TNX"]))

    # VIX requires both level and change
    vix_level = 0.0
    vix_change = 0.0
    if "^VIX" in quotes:
        vix_q = quotes["^VIX"]
        vix_level = vix_q.price
        vix_change = vix_q.pct_change_decimal
        _cast("VIX_level", _vote_vix_level(vix_level))
        _cast("VIX_change", _vote_vix_change(vix_change))

    # --- Optional inputs ---
    if "IWM" in quotes:
        _cast("IWM", _vote_iwm(quotes["IWM"]))
    if "BTC-USD" in quotes:
        _cast("BTC", _vote_btc(quotes["BTC-USD"]))

    confidence = abs(net_score) / total_votes if total_votes > 0 else 0.0
    regime = _classify_regime(net_score, total_votes, confidence, vix_change, vix_level)
    posture = _classify_posture(regime, confidence, vix_level)
    tradeable = posture not in (POSTURE_STAY_FLAT,) and regime != REGIME_CHAOTIC

    logger.info(
        "REGIME | %s | posture=%s | score=%+d/%d | conf=%.2f | VIX=%.1f (%.1f%%)",
        regime, posture, net_score, total_votes, confidence,
        vix_level, vix_change * 100,
    )

    return RegimeState(
        regime=regime,
        posture=posture,
        confidence=confidence,
        net_score=net_score,
        total_votes=total_votes,
        vote_breakdown=vote_breakdown,
        vix_level=vix_level,
        vix_change=vix_change,
        tradeable=tradeable,
        computed_at_utc=now_utc,
    )


# ---------------------------------------------------------------------------
# Layer 3 bridge — build quotes dict from validated results only
# ---------------------------------------------------------------------------

def from_validation_results(
    results: "list[ValidationResult]",
) -> dict[str, NormalizedQuote]:
    """
    Filter Layer 3 output to only passed quotes.
    Failed symbols are silently excluded — their absence means no vote is cast,
    which is the correct behaviour for optional inputs.
    For required inputs (HALT_SYMBOLS), the pipeline should have already halted
    before this function is reached if validation failed.
    """
    from signal_forge.validation import ValidationResult  # avoid circular at module level
    return {
        r.symbol: r.quote
        for r in results
        if r.passed and r.quote is not None
    }


# ---------------------------------------------------------------------------
# Terminal display
# ---------------------------------------------------------------------------

_VOTE_LABEL = {+1: "+1 (risk-on)", -1: "-1 (risk-off)", 0: " 0 (neutral)"}

# Canonical order for all 8 inputs — gate check verifies this set is complete
_EXPECTED_VOTE_KEYS = {"SPY", "QQQ", "IWM", "VIX_level", "VIX_change", "DXY", "TNX", "BTC"}


def print_regime(state: RegimeState) -> None:
    """Print full regime state and vote breakdown to stdout."""
    ts = state.computed_at_utc.strftime("%Y-%m-%d %H:%M UTC")
    tradeable_str = "YES" if state.tradeable else "NO"

    print(f"\n── Macro Regime Engine ─── {ts} ──────────────────────────────")
    print(f"  Regime       : {state.regime}")
    print(f"  Posture      : {state.posture}")
    print(f"  Confidence   : {state.confidence:.0%}  (score {state.net_score:+d} / {state.total_votes} votes)")
    print(f"  VIX          : {state.vix_level:.2f}  ({state.vix_change:+.2%})")
    print(f"  Tradeable    : {tradeable_str}")
    print()
    print("  Vote breakdown:")

    # Print in canonical order, then any extras
    printed: set[str] = set()
    for key in ["SPY", "QQQ", "IWM", "VIX_level", "VIX_change", "DXY", "TNX", "BTC"]:
        if key in state.vote_breakdown:
            v = state.vote_breakdown[key]
            print(f"    {key:<12}  {_VOTE_LABEL.get(v, str(v))}")
            printed.add(key)
        else:
            print(f"    {key:<12}  !! MISSING — no data")

    for key, v in state.vote_breakdown.items():
        if key not in printed:
            print(f"    {key:<12}  {_VOTE_LABEL.get(v, str(v))}")

    print("────────────────────────────────────────────────────────────────\n")


# ---------------------------------------------------------------------------
# Gate check
# ---------------------------------------------------------------------------

def gate_check(state: RegimeState) -> bool:
    """
    Verify the RegimeState meets Phase 3 gate requirements:
    1. All 8 expected vote keys are present in vote_breakdown.
    2. Regime and posture are valid constants.
    3. Confidence is in [0, 1].

    Prints pass/fail per check. Returns True if all pass.
    """
    failures: list[str] = []

    # Check 1: all 8 inputs present
    missing = _EXPECTED_VOTE_KEYS - set(state.vote_breakdown.keys())
    if missing:
        failures.append(f"Missing vote inputs: {sorted(missing)}")

    # Check 2: valid regime constant
    valid_regimes = {REGIME_RISK_ON, REGIME_RISK_OFF, REGIME_TRANSITION, REGIME_CHAOTIC}
    if state.regime not in valid_regimes:
        failures.append(f"Unknown regime: {state.regime!r}")

    # Check 3: valid posture constant
    valid_postures = {
        POSTURE_AGGRESSIVE_LONG, POSTURE_CONTROLLED_LONG,
        POSTURE_NEUTRAL_PREMIUM, POSTURE_DEFENSIVE_SHORT, POSTURE_STAY_FLAT,
    }
    if state.posture not in valid_postures:
        failures.append(f"Unknown posture: {state.posture!r}")

    # Check 4: confidence in range
    if not (0.0 <= state.confidence <= 1.0):
        failures.append(f"Confidence out of range: {state.confidence}")

    print("── Phase 3 Gate Check ──────────────────────────────────────────")
    print(f"  All 8 vote inputs present  : {'PASS' if not missing else 'FAIL — ' + str(sorted(missing))}")
    print(f"  Regime is valid constant   : {'PASS' if state.regime in valid_regimes else 'FAIL'}")
    print(f"  Posture is valid constant  : {'PASS' if state.posture in valid_postures else 'FAIL'}")
    print(f"  Confidence in [0, 1]       : {'PASS' if 0.0 <= state.confidence <= 1.0 else 'FAIL'}")
    passed = len(failures) == 0
    print(f"  Result                     : {'GATE PASS ✓' if passed else 'GATE FAIL ✗'}")
    print("────────────────────────────────────────────────────────────────\n")
    return passed
