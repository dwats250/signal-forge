"""
Market Quality classifier.

Regime  = macro direction / backdrop
Quality = tradability / execution environment

These are independent axes. A strong RISK_ON regime can still have CHAOTIC quality
if it's driven by a single headline or a VIX spike reversal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from signal_forge.macro.regime_types import MarketQuality

if TYPE_CHECKING:
    from signal_forge.macro.regime_types import RegimeInputs


def _v(val: float | None, default: float = 0.0) -> float:
    return val if val is not None else default


def classify_market_quality(inp: "RegimeInputs") -> tuple[MarketQuality, list[str]]:
    """
    Returns (MarketQuality, list_of_quality_drivers).

    Scoring: accumulate degradation points.
      0-15  → CLEAN
      16-35 → MIXED
      36+   → CHAOTIC
    """
    degradation = 0
    drivers: list[str] = []

    # VIX behavior
    vix = _v(inp.vix_change_pct)
    if vix > 30:
        degradation += 30
        drivers.append("VIX spike >30% — acute vol event")
    elif vix > 15:
        degradation += 18
        drivers.append("VIX elevated >15% — heightened vol")
    elif vix > 8:
        degradation += 10
        drivers.append("VIX rising >8% — vol expanding")
    elif vix < -10:
        degradation -= 5  # vol crush is a quality tailwind
        drivers.append("VIX compressing — calm conditions")

    # Event risk
    if inp.event_risk_level == "HIGH":
        degradation += 20
        drivers.append("Event risk HIGH — binary outcome window")
    elif inp.event_risk_level == "MEDIUM":
        degradation += 10
        drivers.append("Event risk MEDIUM — headline sensitivity elevated")

    # Headline shock
    if inp.headline_shock_flag:
        degradation += 20
        drivers.append("Headline shock flag — dislocated price action")

    # Large equity moves (intraday stress proxy)
    spy = _v(inp.spy_change_pct)
    if abs(spy) > 3.0:
        degradation += 20
        drivers.append(f"SPY move {spy:+.1f}% — outsized range, thin execution")
    elif abs(spy) > 1.5:
        degradation += 10
        drivers.append(f"SPY move {spy:+.1f}% — elevated range")

    # USD/JPY as carry stress proxy
    usdjpy = _v(inp.usd_jpy_change_pct)
    if abs(usdjpy) > 1.5:
        degradation += 12
        drivers.append(f"USD/JPY move {usdjpy:+.1f}% — carry unwind / FX stress")

    # BTC as liquidity proxy
    btc = _v(inp.btc_change_pct)
    if btc < -8:
        degradation += 12
        drivers.append("BTC -8%+ — risk liquidity drain")

    # Classify
    if degradation <= 15:
        quality = MarketQuality.CLEAN
    elif degradation <= 35:
        quality = MarketQuality.MIXED
    else:
        quality = MarketQuality.CHAOTIC

    return quality, drivers
