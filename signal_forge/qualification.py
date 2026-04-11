"""
Layer 7 — Trade Qualification Engine

Applies a strict 9-gate filter to structure readings.
Only runs on symbols that passed Layers 1-6.

Gate results:
  TRADE      — all 9 gates passed
  WATCHLIST  — exactly 1 non-critical gate failed (condition stated)
  REJECTED   — any critical gate failed OR 2+ non-critical gates failed

Gates (in order):
  [CRITICAL] 1. regime_tradeable    — regime is not STAY_FLAT or CHAOTIC
  [CRITICAL] 2. confidence_floor    — confidence > 0.50
  [CRITICAL] 3. direction_match     — structure direction aligns with regime
  [CRITICAL] 4. structure_qualified — classification is not CHOP
  [NON-CRIT] 5. stop_defined        — stop level can be computed from ATR
  [NON-CRIT] 6. stop_distance       — stop ≥ 1% of price AND ≥ 0.5× ATR14
  [NON-CRIT] 7. risk_reward         — R:R ≥ 2.0
  [NON-CRIT] 8. position_size       — fits within $100–200 max risk budget
  [NON-CRIT] 9. earnings_clear      — no earnings within 5 calendar days
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import yfinance as yf

from signal_forge.derived import DerivedMetrics
from signal_forge.normalization import NormalizedQuote
from signal_forge.regime import (
    POSTURE_STAY_FLAT,
    REGIME_CHAOTIC,
    REGIME_RISK_OFF,
    REGIME_RISK_ON,
    REGIME_TRANSITION,
    RegimeState,
)
from signal_forge.structure import (
    STRUCT_BREAKOUT,
    STRUCT_CHOP,
    StructureReading,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gate names (used in passed/failed lists for auditability)
# ---------------------------------------------------------------------------

GATE_REGIME_TRADEABLE = "regime_tradeable"
GATE_CONFIDENCE       = "confidence_floor"
GATE_DIRECTION_MATCH  = "direction_match"
GATE_STRUCTURE        = "structure_qualified"
GATE_STOP_DEFINED     = "stop_defined"
GATE_STOP_DISTANCE    = "stop_distance"
GATE_RISK_REWARD      = "risk_reward"
GATE_POSITION_SIZE    = "position_size"
GATE_EARNINGS         = "earnings_clear"

CRITICAL_GATES: frozenset[str] = frozenset({
    GATE_REGIME_TRADEABLE,
    GATE_CONFIDENCE,
    GATE_DIRECTION_MATCH,
    GATE_STRUCTURE,
})

NON_CRITICAL_GATES: frozenset[str] = frozenset({
    GATE_STOP_DEFINED,
    GATE_STOP_DISTANCE,
    GATE_RISK_REWARD,
    GATE_POSITION_SIZE,
    GATE_EARNINGS,
})

# Symbols that cannot have options strategies (excluded from qualification)
_NON_TRADEABLE = {"^VIX", "DX-Y.NYB", "^TNX", "BTC-USD"}

# Qualification constants
_MIN_CONFIDENCE      = 0.50
_MIN_RR              = 2.0
_MIN_STOP_PCT        = 0.01      # 1% of price
_MIN_STOP_ATR_MULT   = 0.5      # stop must be ≥ 0.5× ATR14
_ATR_STOP_MULT       = 1.0      # place stop at 1× ATR14 from entry
_ATR_TARGET_MULT     = 2.0      # target at 2× ATR14 from entry (guarantees R:R = 2.0)
_MAX_RISK_LOW        = 100.0    # dollars
_MAX_RISK_HIGH       = 200.0    # dollars
_EARNINGS_DAYS_CLEAR = 5        # calendar days


# ---------------------------------------------------------------------------
# Output contracts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CandidateSetup:
    symbol: str
    direction: str               # "long" | "short"
    entry: float
    stop: float
    target: float
    stop_distance_pct: float     # |price - stop| / price
    stop_distance_atr: float     # |price - stop| / ATR14
    risk_reward: float
    max_shares_100: float        # shares risking $100
    max_shares_200: float        # shares risking $200
    structure: str
    iv_environment: str
    strategy_preference: str


@dataclass(frozen=True)
class QualificationResult:
    symbol: str
    status: str                          # "TRADE" | "WATCHLIST" | "REJECTED"
    setup: Optional[CandidateSetup]
    gates_passed: list[str]
    gates_failed: list[str]
    watchlist_condition: Optional[str]   # if WATCHLIST: the one failing gate + detail
    rejection_reason: Optional[str]      # if REJECTED: first critical gate failure or summary


# ---------------------------------------------------------------------------
# Direction inference from structure
# ---------------------------------------------------------------------------

def _infer_direction(reading: StructureReading, metrics: DerivedMetrics) -> Optional[str]:
    """
    Infer trade direction from structure.

    Returns "long", "short", or None (ambiguous — cannot qualify).
    """
    alignment = reading.ema_alignment

    if reading.classification == STRUCT_BREAKOUT:
        # Breakout direction follows momentum sign
        mom = metrics.momentum_5d or 0.0
        if mom > 0:
            return "long"
        if mom < 0:
            return "short"
        return None

    # For TREND, PULLBACK, REVERSAL:
    # Reversal goes opposite to current alignment
    if reading.classification == "REVERSAL":
        return "short" if alignment == "bull" else ("long" if alignment == "bear" else None)

    if alignment == "bull":
        return "long"
    if alignment == "bear":
        return "short"
    return None


def _direction_matches_regime(direction: Optional[str], regime: str) -> bool:
    """Long direction requires RISK_ON; short requires RISK_OFF. TRANSITION never matches."""
    if direction is None:
        return False
    if regime == REGIME_RISK_ON:
        return direction == "long"
    if regime == REGIME_RISK_OFF:
        return direction == "short"
    return False  # TRANSITION and CHAOTIC never qualify


# ---------------------------------------------------------------------------
# Setup generation
# ---------------------------------------------------------------------------

def _build_setup(
    symbol: str,
    direction: str,
    price: float,
    atr14: float,
    reading: StructureReading,
) -> CandidateSetup:
    """
    Build a CandidateSetup from ATR-derived stop and target.
    Stop = 1× ATR from entry; Target = 2× ATR from entry → R:R = 2.0.
    """
    stop_dist = _ATR_STOP_MULT * atr14
    target_dist = _ATR_TARGET_MULT * atr14

    if direction == "long":
        stop   = price - stop_dist
        target = price + target_dist
    else:
        stop   = price + stop_dist
        target = price - target_dist

    stop_pct     = abs(price - stop) / price
    stop_atr     = abs(price - stop) / atr14 if atr14 > 0 else 0.0
    rr           = target_dist / stop_dist if stop_dist > 0 else 0.0
    stop_dollars = abs(price - stop)
    shares_100   = _MAX_RISK_LOW  / stop_dollars if stop_dollars > 0 else 0.0
    shares_200   = _MAX_RISK_HIGH / stop_dollars if stop_dollars > 0 else 0.0

    return CandidateSetup(
        symbol=symbol,
        direction=direction,
        entry=price,
        stop=round(stop, 4),
        target=round(target, 4),
        stop_distance_pct=stop_pct,
        stop_distance_atr=stop_atr,
        risk_reward=rr,
        max_shares_100=shares_100,
        max_shares_200=shares_200,
        structure=reading.classification,
        iv_environment=reading.iv_environment,
        strategy_preference=reading.strategy_preference,
    )


# ---------------------------------------------------------------------------
# Earnings check
# ---------------------------------------------------------------------------

def _earnings_clear(symbol: str, days: int = _EARNINGS_DAYS_CLEAR) -> tuple[bool, str]:
    """
    Check whether earnings fall within the next `days` calendar days.
    Returns (clear, detail_string).

    Passes the gate if:
    - No earnings found within the window
    - yfinance calendar is unavailable (fail-open: don't block on missing data)

    The fail-open choice avoids phantom watchlist noise from calendar API failures.
    If a known earnings date IS found within the window, gate fails.
    """
    try:
        ticker = yf.Ticker(symbol)
        cal = ticker.calendar

        # yfinance returns None or empty dict when no data available
        if not cal:
            return True, "calendar unavailable — pass"

        now = datetime.now(tz=timezone.utc)
        cutoff = now + timedelta(days=days)

        # Calendar dict has 'Earnings Date' as a list of Timestamps
        earnings_dates = cal.get("Earnings Date", [])
        if not earnings_dates:
            return True, "no earnings dates found"

        # Normalize to a flat list regardless of whether it's a list or scalar
        if not isinstance(earnings_dates, list):
            earnings_dates = [earnings_dates]

        for ed in earnings_dates:
            try:
                # yfinance returns pandas Timestamp — convert to aware datetime
                import pandas as pd
                if isinstance(ed, pd.Timestamp):
                    ed_dt = ed.to_pydatetime()
                    if ed_dt.tzinfo is None:
                        ed_dt = ed_dt.replace(tzinfo=timezone.utc)
                    if now <= ed_dt <= cutoff:
                        return False, f"earnings {ed_dt.date()} within {days}d window"
            except Exception:
                continue

        return True, "no earnings within window"

    except Exception as exc:
        logger.debug("Earnings check failed for %s: %s — passing gate", symbol, exc)
        return True, f"calendar error ({exc}) — pass"


# ---------------------------------------------------------------------------
# Single-symbol qualification
# ---------------------------------------------------------------------------

def _qualify_one(
    symbol: str,
    quote: NormalizedQuote,
    reading: StructureReading,
    metrics: DerivedMetrics,
    regime: RegimeState,
) -> QualificationResult:
    """Run all 9 gates for one symbol. Returns a QualificationResult."""

    gates_passed: list[str] = []
    gates_failed: list[str] = []

    def pass_(gate: str) -> None:
        gates_passed.append(gate)

    def fail_(gate: str) -> None:
        gates_failed.append(gate)

    # ── Gate 1: regime tradeable ─────────────────────────────────────────
    if regime.tradeable and regime.regime != REGIME_CHAOTIC and regime.posture != POSTURE_STAY_FLAT:
        pass_(GATE_REGIME_TRADEABLE)
    else:
        fail_(GATE_REGIME_TRADEABLE)
        return QualificationResult(
            symbol=symbol, status="REJECTED",
            setup=None,
            gates_passed=gates_passed, gates_failed=gates_failed,
            watchlist_condition=None,
            rejection_reason=f"regime={regime.regime} posture={regime.posture} — no trade",
        )

    # ── Gate 2: confidence floor ─────────────────────────────────────────
    if regime.confidence > _MIN_CONFIDENCE:
        pass_(GATE_CONFIDENCE)
    else:
        fail_(GATE_CONFIDENCE)
        return QualificationResult(
            symbol=symbol, status="REJECTED",
            setup=None,
            gates_passed=gates_passed, gates_failed=gates_failed,
            watchlist_condition=None,
            rejection_reason=f"confidence {regime.confidence:.0%} ≤ {_MIN_CONFIDENCE:.0%} floor",
        )

    # ── Gate 3: direction match ───────────────────────────────────────────
    direction = _infer_direction(reading, metrics)
    if _direction_matches_regime(direction, regime.regime):
        pass_(GATE_DIRECTION_MATCH)
    else:
        fail_(GATE_DIRECTION_MATCH)
        return QualificationResult(
            symbol=symbol, status="REJECTED",
            setup=None,
            gates_passed=gates_passed, gates_failed=gates_failed,
            watchlist_condition=None,
            rejection_reason=(
                f"direction={direction} does not match regime={regime.regime}"
            ),
        )

    # ── Gate 4: structure qualified ───────────────────────────────────────
    if reading.classification != STRUCT_CHOP and not reading.disqualified:
        pass_(GATE_STRUCTURE)
    else:
        fail_(GATE_STRUCTURE)
        return QualificationResult(
            symbol=symbol, status="REJECTED",
            setup=None,
            gates_passed=gates_passed, gates_failed=gates_failed,
            watchlist_condition=None,
            rejection_reason=f"structure={reading.classification} — disqualified",
        )

    # ── Build candidate setup (required for non-critical gate evaluation) ─
    atr14 = metrics.atr14
    if atr14 is None or atr14 <= 0 or direction is None:
        fail_(GATE_STOP_DEFINED)
        return QualificationResult(
            symbol=symbol, status="REJECTED",
            setup=None,
            gates_passed=gates_passed, gates_failed=gates_failed,
            watchlist_condition=None,
            rejection_reason="ATR14 unavailable — cannot define stop",
        )

    setup = _build_setup(symbol, direction, quote.price, atr14, reading)
    pass_(GATE_STOP_DEFINED)

    # ── Non-critical gates (collect all failures) ─────────────────────────
    nc_failures: list[tuple[str, str]] = []   # (gate_name, detail)

    # Gate 6: stop distance
    stop_pct_ok  = setup.stop_distance_pct >= _MIN_STOP_PCT
    stop_atr_ok  = setup.stop_distance_atr >= _MIN_STOP_ATR_MULT
    if stop_pct_ok and stop_atr_ok:
        pass_(GATE_STOP_DISTANCE)
    else:
        fail_(GATE_STOP_DISTANCE)
        detail = (
            f"stop_pct={setup.stop_distance_pct:.2%} (need ≥{_MIN_STOP_PCT:.0%}), "
            f"stop_atr={setup.stop_distance_atr:.2f}× (need ≥{_MIN_STOP_ATR_MULT}×)"
        )
        nc_failures.append((GATE_STOP_DISTANCE, detail))

    # Gate 7: R:R
    if setup.risk_reward >= _MIN_RR:
        pass_(GATE_RISK_REWARD)
    else:
        fail_(GATE_RISK_REWARD)
        nc_failures.append((GATE_RISK_REWARD, f"R:R={setup.risk_reward:.2f} (need ≥{_MIN_RR})"))

    # Gate 8: position size — at least 1 share fits in $100 risk budget
    size_ok = setup.max_shares_100 >= 1.0
    if size_ok:
        pass_(GATE_POSITION_SIZE)
    else:
        fail_(GATE_POSITION_SIZE)
        nc_failures.append((
            GATE_POSITION_SIZE,
            f"stop_dollars={setup.stop_distance_pct * quote.price:.2f} — "
            f"max_shares_100={setup.max_shares_100:.2f} < 1",
        ))

    # Gate 9: earnings
    earnings_ok, earnings_detail = _earnings_clear(symbol)
    if earnings_ok:
        pass_(GATE_EARNINGS)
    else:
        fail_(GATE_EARNINGS)
        nc_failures.append((GATE_EARNINGS, earnings_detail))

    # ── Final verdict ─────────────────────────────────────────────────────
    if len(nc_failures) == 0:
        return QualificationResult(
            symbol=symbol, status="TRADE",
            setup=setup,
            gates_passed=gates_passed, gates_failed=gates_failed,
            watchlist_condition=None,
            rejection_reason=None,
        )

    if len(nc_failures) == 1:
        gate_name, detail = nc_failures[0]
        return QualificationResult(
            symbol=symbol, status="WATCHLIST",
            setup=setup,
            gates_passed=gates_passed, gates_failed=gates_failed,
            watchlist_condition=f"{gate_name}: {detail}",
            rejection_reason=None,
        )

    # 2+ non-critical gate failures
    summary = " | ".join(f"{n}: {d}" for n, d in nc_failures)
    return QualificationResult(
        symbol=symbol, status="REJECTED",
        setup=setup,
        gates_passed=gates_passed, gates_failed=gates_failed,
        watchlist_condition=None,
        rejection_reason=summary,
    )


# ---------------------------------------------------------------------------
# Batch qualification
# ---------------------------------------------------------------------------

def qualify_all(
    quotes: dict[str, NormalizedQuote],
    readings: dict[str, StructureReading],
    metrics: dict[str, DerivedMetrics],
    regime: RegimeState,
) -> list[QualificationResult]:
    """
    Run qualification for all eligible symbols.

    Excludes non-tradeable macro instruments (VIX, DXY, TNX, BTC).
    All other symbols in readings are evaluated.
    Results are sorted: TRADE first, then WATCHLIST, then REJECTED.
    """
    results: list[QualificationResult] = []

    for symbol, reading in readings.items():
        if symbol in _NON_TRADEABLE:
            continue
        quote = quotes.get(symbol)
        m = metrics.get(symbol)
        if quote is None or m is None:
            logger.debug("QUAL SKIP %s — missing quote or metrics", symbol)
            continue

        result = _qualify_one(symbol, quote, reading, m, regime)
        results.append(result)

        if result.status == "REJECTED":
            logger.info("QUAL REJECTED  | %s | %s", symbol, result.rejection_reason)
        elif result.status == "WATCHLIST":
            logger.info("QUAL WATCHLIST | %s | %s", symbol, result.watchlist_condition)
        elif result.status == "TRADE":
            logger.info("QUAL TRADE     | %s | dir=%s entry=%.2f stop=%.2f target=%.2f",
                        symbol, result.setup.direction, result.setup.entry,
                        result.setup.stop, result.setup.target)

    # Sort: TRADE → WATCHLIST → REJECTED
    _order = {"TRADE": 0, "WATCHLIST": 1, "REJECTED": 2}
    results.sort(key=lambda r: _order.get(r.status, 9))
    return results


# ---------------------------------------------------------------------------
# Terminal report
# ---------------------------------------------------------------------------

def print_qualification_report(
    results: list[QualificationResult],
    regime: RegimeState,
    chop_log: list[str],
) -> None:
    """
    Print a structured qualification report to stdout.

    chop_log: list of symbol names that were classified CHOP before reaching
              qualification (passed in from structure engine output).
    """
    trades     = [r for r in results if r.status == "TRADE"]
    watchlist  = [r for r in results if r.status == "WATCHLIST"]
    rejected   = [r for r in results if r.status == "REJECTED"]

    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n══ Trade Qualification Report ═══ {ts} ═══════════════════════════")
    print(f"  Regime    : {regime.regime}  Posture: {regime.posture}")
    print(f"  Confidence: {regime.confidence:.0%}  VIX: {regime.vix_level:.2f}")
    print()

    # CHOP log — only tradeable symbols (exclude macro instruments)
    tradeable_chop = [s for s in chop_log if s not in _NON_TRADEABLE and not s.startswith("^")]
    if tradeable_chop:
        print(f"  CHOP (disqualified — {len(tradeable_chop)} ticker(s)):")
        for sym in sorted(tradeable_chop):
            print(f"    ✗ {sym}")
        print()

    # TRADE
    print(f"  VALIDATED TRADES ({len(trades)}):")
    if trades:
        for r in trades:
            s = r.setup
            print(f"    ✓ {s.symbol:<8}  {s.direction.upper():<5}  "
                  f"entry={s.entry:.2f}  stop={s.stop:.2f}  "
                  f"target={s.target:.2f}  R:R={s.risk_reward:.1f}  "
                  f"{s.iv_environment}  {s.strategy_preference}")
    else:
        print("    — none —")
    print()

    # WATCHLIST
    print(f"  WATCHLIST ({len(watchlist)}):")
    if watchlist:
        for r in watchlist:
            s = r.setup
            print(f"    ~ {s.symbol:<8}  {s.direction.upper():<5}  "
                  f"entry={s.entry:.2f}  | condition: {r.watchlist_condition}")
    else:
        print("    — none —")
    print()

    # REJECTED summary (brief — detail is in logs)
    print(f"  REJECTED ({len(rejected)}):")
    for r in rejected:
        reason = r.rejection_reason or "—"
        # Truncate long multi-gate reasons
        if len(reason) > 80:
            reason = reason[:77] + "..."
        print(f"    ✗ {r.symbol:<8}  {reason}")

    print("═" * 72 + "\n")
