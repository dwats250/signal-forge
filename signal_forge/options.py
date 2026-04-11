"""
Layer 8 — Options Expression Engine

Maps each qualified setup → concrete options strategy.
No live options chain access — strikes are relative (ATM, 1_ITM).
Expiry range derived from momentum_5d.
Size: floor(150 / (spread_width × 100)). Reject if max_contracts < 1.
Exit: +50% profit target OR full debit loss on every trade.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Optional

from signal_forge.qualification import CandidateSetup, QualificationResult
from signal_forge.structure import (
    IV_ELEVATED,
    IV_HIGH,
    IV_LOW,
    IV_NORMAL,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Risk budget for sizing
_RISK_BUDGET = 150.0                        # dollars

# Max spread width by instrument class
_INDEX_ETF = {"SPY", "QQQ", "IWM"}
_MAX_SPREAD_WIDTH: dict[str, float] = {
    "SPY": 5.0, "QQQ": 5.0, "IWM": 5.0,    # per PRD
    "default": 2.50,
}

# Working spread width — smallest width that keeps max_contracts ≥ 1
# floor(150 / (width × 100)) ≥ 1  →  width ≤ 150/100 = 1.50
# We use $1.00 as the default; this gives exactly 1 contract at $100 max risk.
_WORKING_SPREAD_WIDTH = 1.00

# Strike rounding increment per instrument (nearest tradeable strike)
_STRIKE_INCREMENT: dict[str, float] = {
    "SPY": 1.0, "QQQ": 1.0, "IWM": 1.0,
    "default": 1.0,
}

# DTE ranges by momentum strength (absolute value of momentum_5d)
_DTE_STRONG    = (7,  14)   # |momentum| > 5%
_DTE_MODERATE  = (14, 21)   # |momentum| > 2%
_DTE_WEAK      = (21, 30)   # otherwise

# Exit rules
_EXIT_PROFIT_PCT = 0.50     # +50% of premium received / debit paid
_EXIT_LOSS       = "full_debit"


# ---------------------------------------------------------------------------
# Strategy name constants
# ---------------------------------------------------------------------------

LONG_CALL_SPREAD = "long_call_spread"   # debit, bull — buy lower call, sell higher call
BULL_PUT_SPREAD  = "bull_put_spread"    # credit, bull — sell higher put, buy lower put
LONG_PUT_SPREAD  = "long_put_spread"    # debit, bear — buy higher put, sell lower put
BEAR_CALL_SPREAD = "bear_call_spread"   # credit, bear — sell lower call, buy higher call


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OptionsExpression:
    symbol: str
    strategy: str               # one of the 4 STRATEGY constants above
    direction: str              # "long" | "short"
    iv_environment: str
    long_strike: float          # strike we buy
    short_strike: float         # strike we sell
    spread_width: float         # |long_strike - short_strike|
    dte_min: int
    dte_max: int
    max_contracts: int
    max_risk_dollars: float     # spread_width × 100 × max_contracts
    exit_profit_target: str     # human-readable exit description
    exit_loss: str              # "full_debit" or "full_credit_loss"
    size_reduced: bool          # True when HIGH_IV applies 50% size reduction
    entry: float
    stop: float
    target: float
    structure: str


# ---------------------------------------------------------------------------
# Strategy matrix
# ---------------------------------------------------------------------------

def _select_strategy(direction: str, iv_env: str) -> str:
    """
    Map direction × IV environment → strategy.

    Long bias:
      LOW_IV  → long_call_spread (debit — options cheap)
      NORMAL  → bull_put_spread  (credit — default to credit when IV neutral)
      ELEVATED → bull_put_spread  (credit — sell elevated premium)
      HIGH    → bull_put_spread  (credit, size reduced)

    Short bias:
      LOW_IV  → long_put_spread  (debit)
      NORMAL  → bear_call_spread (credit)
      ELEVATED → bear_call_spread (credit)
      HIGH    → bear_call_spread (credit, size reduced)
    """
    if direction == "long":
        return LONG_CALL_SPREAD if iv_env == IV_LOW else BULL_PUT_SPREAD
    else:
        return LONG_PUT_SPREAD if iv_env == IV_LOW else BEAR_CALL_SPREAD


# ---------------------------------------------------------------------------
# Strike selection
# ---------------------------------------------------------------------------

def _atm_strike(price: float, increment: float) -> float:
    """Round price to nearest strike increment."""
    return round(price / increment) * increment


def _select_strikes(
    strategy: str,
    atm: float,
    spread_width: float,
) -> tuple[float, float]:
    """
    Return (long_strike, short_strike) for the given strategy.

    long_call_spread: buy ATM call, sell (ATM + width) call
    bull_put_spread:  sell ATM put,  buy (ATM - width) put  [long = protective put]
    long_put_spread:  buy ATM put,   sell (ATM - width) put
    bear_call_spread: sell ATM call, buy (ATM + width) call [long = protective call]
    """
    if strategy == LONG_CALL_SPREAD:
        return atm, atm + spread_width                # long lower, short higher
    elif strategy == BULL_PUT_SPREAD:
        return atm - spread_width, atm                # long lower, short higher
    elif strategy == LONG_PUT_SPREAD:
        return atm, atm - spread_width                # long higher, short lower
    else:  # BEAR_CALL_SPREAD
        return atm + spread_width, atm                # long higher, short lower


# ---------------------------------------------------------------------------
# DTE selection
# ---------------------------------------------------------------------------

def _select_dte(momentum_5d: Optional[float]) -> tuple[int, int]:
    mom = abs(momentum_5d) if momentum_5d is not None else 0.0
    if mom > 0.05:
        return _DTE_STRONG
    if mom > 0.02:
        return _DTE_MODERATE
    return _DTE_WEAK


# ---------------------------------------------------------------------------
# Sizing
# ---------------------------------------------------------------------------

def _compute_size(spread_width: float, high_iv: bool) -> tuple[int, float]:
    """
    Return (max_contracts, max_risk_dollars).
    Formula: floor(150 / (spread_width × 100))
    HIGH_IV applies 50% size reduction (floor before halving).
    Returns (0, 0) if budget does not fit even 1 contract.
    """
    raw = math.floor(_RISK_BUDGET / (spread_width * 100.0))
    if high_iv:
        raw = math.floor(raw / 2)
    max_risk = spread_width * 100.0 * raw
    return raw, max_risk


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def express(qual: QualificationResult) -> Optional[OptionsExpression]:
    """
    Map a TRADE-status QualificationResult to an OptionsExpression.
    Returns None if sizing fails (max_contracts < 1) — caller should log and reject.
    """
    if qual.status != "TRADE" or qual.setup is None:
        return None

    setup: CandidateSetup = qual.setup
    symbol = setup.symbol
    direction = setup.direction
    iv_env = setup.iv_environment
    high_iv = iv_env == IV_HIGH
    momentum = None  # not directly on setup — we derive from structure context

    strategy = _select_strategy(direction, iv_env)

    # Spread width: use working width capped at instrument maximum
    max_width = _MAX_SPREAD_WIDTH.get(symbol, _MAX_SPREAD_WIDTH["default"])
    spread_width = min(_WORKING_SPREAD_WIDTH, max_width)

    # Sizing
    max_contracts, max_risk = _compute_size(spread_width, high_iv)
    if max_contracts < 1:
        logger.warning(
            "OPTIONS REJECT | %s | max_contracts=0 | spread_width=%.2f | budget=%.0f",
            symbol, spread_width, _RISK_BUDGET,
        )
        return None

    # Strike selection
    increment = _STRIKE_INCREMENT.get(symbol, _STRIKE_INCREMENT["default"])
    atm = _atm_strike(setup.entry, increment)
    long_strike, short_strike = _select_strikes(strategy, atm, spread_width)

    # DTE — use structure-level momentum approximation from stop/target spread
    # Proxy for momentum: (target - entry) / entry
    momentum_proxy = (abs(setup.target - setup.entry) / setup.entry) if setup.entry > 0 else 0.0
    dte_min, dte_max = _select_dte(momentum_proxy)

    exit_profit = f"+{_EXIT_PROFIT_PCT:.0%} of premium paid/received"
    exit_loss = "full debit loss" if strategy in (LONG_CALL_SPREAD, LONG_PUT_SPREAD) else "full credit loss"

    logger.info(
        "OPTIONS | %s | %s | strikes=%s/%s | width=%.2f | contracts=%d | DTE=%d-%d | IV=%s",
        symbol, strategy, long_strike, short_strike,
        spread_width, max_contracts, dte_min, dte_max, iv_env,
    )

    return OptionsExpression(
        symbol=symbol,
        strategy=strategy,
        direction=direction,
        iv_environment=iv_env,
        long_strike=long_strike,
        short_strike=short_strike,
        spread_width=spread_width,
        dte_min=dte_min,
        dte_max=dte_max,
        max_contracts=max_contracts,
        max_risk_dollars=max_risk,
        exit_profit_target=exit_profit,
        exit_loss=exit_loss,
        size_reduced=high_iv,
        entry=setup.entry,
        stop=setup.stop,
        target=setup.target,
        structure=setup.structure,
    )


def express_all(qual_results: list[QualificationResult]) -> list[OptionsExpression]:
    """
    Map all TRADE-status results to OptionsExpressions.
    Drops any result where sizing fails (max_contracts < 1).
    """
    out: list[OptionsExpression] = []
    for q in qual_results:
        if q.status != "TRADE":
            continue
        expr = express(q)
        if expr is not None:
            out.append(expr)
        else:
            logger.warning("OPTIONS SIZED-OUT | %s — dropped from trade list", q.symbol)
    return out
