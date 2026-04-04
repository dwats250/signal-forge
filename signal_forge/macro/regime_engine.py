"""
Market Regime Engine — main entry point.

classify_market_regime(inputs) -> RegimeDecision

Pipeline:
  1. Score all candidate regimes via weighted rules
  2. Select highest-scoring regime
  3. Compute confidence from score separation
  4. Classify market quality independently
  5. Map (regime, quality) → execution posture
  6. Attach drivers, themes, tailwinds, headwinds
"""

from __future__ import annotations

from signal_forge.macro.execution_posture import get_execution_posture
from signal_forge.macro.market_quality import classify_market_quality
from signal_forge.macro.regime_rules import REGIME_SCORERS
from signal_forge.macro.regime_types import (
    Regime,
    RegimeDecision,
    RegimeInputs,
)

# ─── Theme catalog ────────────────────────────────────────────────────────────

_FAVORED: dict[str, list[str]] = {
    "RISK_ON":             ["Growth equities", "Small caps (IWM)", "Cyclicals", "High beta", "BTC/crypto"],
    "RISK_OFF":            ["Treasuries", "Gold", "Utilities", "Defensives", "Yen"],
    "INFLATION_SHOCK":     ["Energy (XLE)", "Commodities", "TIPS", "Materials", "Inflation hedges"],
    "GROWTH_SCARE":        ["Treasuries", "Gold", "Defensives", "Inverse ETFs"],
    "COMMODITY_EXPANSION": ["Energy", "Base metals", "Agriculture", "Miners", "Materials"],
    "METALS_BID":          ["Gold miners (GDX)", "Silver", "Precious metals royalties", "Gold ETFs"],
    "LIQUIDITY_STRESS":    ["Cash", "Short duration", "Volatility long"],
    "MIXED":               ["High-conviction single names", "Event-driven setups"],
}

_DISFAVORED: dict[str, list[str]] = {
    "RISK_ON":             ["Long vol", "Treasuries", "Inverse ETFs", "Yen longs"],
    "RISK_OFF":            ["High-beta growth", "BTC/crypto", "Cyclicals", "Leveraged longs"],
    "INFLATION_SHOCK":     ["Long-duration bonds", "Consumer discretionary", "Rate-sensitive tech"],
    "GROWTH_SCARE":        ["Cyclicals", "Oil longs", "Financials", "Small caps"],
    "COMMODITY_EXPANSION": ["Consumer staples", "Dollar-linked assets", "Bond longs"],
    "METALS_BID":          ["Dollar longs", "High-rate beneficiaries", "Short gold"],
    "LIQUIDITY_STRESS":    ["All new risk", "Leveraged positions", "Illiquid names"],
    "MIXED":               ["High leverage", "Low-liquidity names", "Theme plays"],
}

_TAILWINDS: dict[str, list[str]] = {
    "RISK_ON":             ["Risk appetite elevated", "Liquidity ample", "Vol suppressed"],
    "RISK_OFF":            ["Safety demand active", "Hedges in play", "Vol premium available"],
    "INFLATION_SHOCK":     ["Energy/commodity names repricing", "Inflation premium expanding"],
    "GROWTH_SCARE":        ["Rate cut expectations building", "Safe-haven flows active"],
    "COMMODITY_EXPANSION": ["Demand cycle active", "Dollar weakness", "Supply constraints priced"],
    "METALS_BID":          ["Real rates negative/falling", "Dollar soft", "Sovereign demand"],
    "LIQUIDITY_STRESS":    ["Vol long positions profitable", "Drawdown protection active"],
    "MIXED":               ["Idiosyncratic setups viable", "Sector rotation opportunities"],
}

_HEADWINDS: dict[str, list[str]] = {
    "RISK_ON":             ["Any macro shock could reverse quickly", "Complacency risk"],
    "RISK_OFF":            ["Short squeezes in beaten names", "Policy reversal risk"],
    "INFLATION_SHOCK":     ["Demand destruction risk", "Policy overtightening risk"],
    "GROWTH_SCARE":        ["Forced selling across asset classes", "Credit spreads widening"],
    "COMMODITY_EXPANSION": ["Dollar reversal risk", "Global demand slowdown"],
    "METALS_BID":          ["Rate reversal could cap metals", "Profit-taking after run"],
    "LIQUIDITY_STRESS":    ["Forced liquidation continues", "Gap risk on all positions"],
    "MIXED":               ["No dominant bid — execution timing critical", "False breakouts likely"],
}


# ─── Engine ──────────────────────────────────────────────────────────────────

def classify_market_regime(inputs: RegimeInputs) -> RegimeDecision:
    """
    Classify the current market regime from a cross-asset snapshot.
    Returns a RegimeDecision ready for downstream posture / filter use.
    """
    # 1. Score all regimes
    regime_scores: dict[str, float] = {}
    regime_drivers: dict[str, list[str]] = {}

    for name, scorer in REGIME_SCORERS.items():
        hits = scorer(inputs)
        total = sum(s for s, _ in hits)
        labels = [label for s, label in hits if s > 0]
        regime_scores[name] = total
        regime_drivers[name] = labels

    # 2. Select winner
    top_name = max(regime_scores, key=lambda k: regime_scores[k])
    top_score = regime_scores[top_name]

    # 3. Confidence: normalized separation between top and second
    sorted_scores = sorted(regime_scores.values(), reverse=True)
    second_score = sorted_scores[1] if len(sorted_scores) > 1 else 0.0
    if top_score > 0:
        confidence = min(1.0, (top_score - second_score) / max(top_score, 1))
    else:
        confidence = 0.0

    regime = Regime(top_name)

    # 4. Market quality (independent axis)
    quality, quality_drivers = classify_market_quality(inputs)

    # 5. Execution posture
    posture = get_execution_posture(regime, quality)

    # 6. Build output
    drivers = regime_drivers[top_name][:5]  # top 5 regime drivers

    # Append quality context if degraded
    if quality_drivers and quality.value != "CLEAN":
        drivers.append(f"Quality: {quality.value} — {quality_drivers[0]}")

    notes_parts = []
    if confidence < 0.25:
        notes_parts.append("Low separation — regime conviction weak, lean conservative")
    if top_score < 20:
        notes_parts.append("Low absolute score — sparse inputs, treat as MIXED")
    if inputs.headline_shock_flag:
        notes_parts.append("Headline shock flag active — posture floors at DEFENSIVE")
    notes = ". ".join(notes_parts) if notes_parts else f"{regime.value} regime, {quality.value} quality"

    return RegimeDecision(
        regime=regime,
        regime_confidence=round(confidence, 3),
        market_quality=quality,
        execution_posture=posture,
        drivers=drivers,
        favored_themes=_FAVORED.get(top_name, []),
        disfavored_themes=_DISFAVORED.get(top_name, []),
        tailwinds=_TAILWINDS.get(top_name, []),
        headwinds=_HEADWINDS.get(top_name, []),
        notes=notes,
        raw_scores=regime_scores,
    )
