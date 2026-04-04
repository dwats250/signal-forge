"""
Tests for the Market Regime Engine.

Covers:
  1. Clear RISK_ON case
  2. Clear RISK_OFF case
  3. INFLATION_SHOCK case
  4. METALS_BID case
  5. MIXED / fragmented case
  6. CHAOTIC quality downgrade
  7. Missing-input resilience
"""

import pytest

from signal_forge.macro import classify_market_regime
from signal_forge.macro.regime_types import (
    ExecutionPosture,
    MarketQuality,
    Regime,
    RegimeInputs,
)


# ─── 1. RISK_ON ───────────────────────────────────────────────────────────────

def test_risk_on_clean():
    inp = RegimeInputs(
        dxy_change_pct=-0.6,
        spy_change_pct=1.2,
        qqq_change_pct=1.4,
        iwm_change_pct=0.8,
        vix_change_pct=-12.0,
        us10y_change_bp=4.0,
        gold_change_pct=-0.1,
        usd_jpy_change_pct=0.5,
    )
    d = classify_market_regime(inp)
    assert d.regime == Regime.RISK_ON
    assert d.market_quality == MarketQuality.CLEAN
    assert d.execution_posture == ExecutionPosture.AGGRESSIVE
    assert any("SPY" in drv or "DXY" in drv or "VIX" in drv for drv in d.drivers)


# ─── 2. RISK_OFF ──────────────────────────────────────────────────────────────

def test_risk_off():
    inp = RegimeInputs(
        dxy_change_pct=0.8,
        spy_change_pct=-1.8,
        qqq_change_pct=-2.1,
        vix_change_pct=22.0,
        us10y_change_bp=-15.0,
        gold_change_pct=1.2,
        usd_jpy_change_pct=-0.9,
    )
    d = classify_market_regime(inp)
    assert d.regime == Regime.RISK_OFF
    assert d.execution_posture in {ExecutionPosture.SELECTIVE, ExecutionPosture.DEFENSIVE, ExecutionPosture.NO_DEPLOY}
    assert any("VIX" in drv or "SPY" in drv or "10Y" in drv for drv in d.drivers)


# ─── 3. INFLATION_SHOCK ───────────────────────────────────────────────────────

def test_inflation_shock():
    inp = RegimeInputs(
        oil_change_pct=4.5,
        us2y_change_bp=18.0,
        us10y_change_bp=16.0,
        dxy_change_pct=0.6,
        spy_change_pct=-0.8,
        copper_change_pct=2.2,
        gold_change_pct=0.9,
    )
    d = classify_market_regime(inp)
    assert d.regime == Regime.INFLATION_SHOCK
    assert d.execution_posture in {ExecutionPosture.SELECTIVE, ExecutionPosture.DEFENSIVE, ExecutionPosture.NO_DEPLOY}
    assert any("oil" in drv.lower() or "yield" in drv.lower() or "inflation" in drv.lower() for drv in d.drivers)


# ─── 4. METALS_BID ───────────────────────────────────────────────────────────

def test_metals_bid():
    inp = RegimeInputs(
        gold_change_pct=2.1,
        gdx_change_pct=3.4,
        silver_change_pct=2.8,
        dxy_change_pct=-0.5,
        us2y_change_bp=-8.0,
        us10y_change_bp=-6.0,
        vix_change_pct=3.0,
    )
    d = classify_market_regime(inp)
    assert d.regime == Regime.METALS_BID
    assert d.execution_posture in {ExecutionPosture.AGGRESSIVE, ExecutionPosture.SELECTIVE}
    assert any("gold" in drv.lower() or "GDX" in drv or "silver" in drv.lower() for drv in d.drivers)


# ─── 5. MIXED / fragmented ───────────────────────────────────────────────────

def test_mixed_fragmented():
    # Genuinely fragmented: dollar + equities both bid (contradictory),
    # IWM lagging SPY (bifurcation), gold flat, no clear commodity or rate signal.
    inp = RegimeInputs(
        spy_change_pct=0.7,
        iwm_change_pct=-0.8,      # small caps lagging — bifurcated
        dxy_change_pct=0.8,       # dollar + equities both up — unstable
        us10y_change_bp=3.0,
        gold_change_pct=0.2,
        vix_change_pct=1.0,
    )
    d = classify_market_regime(inp)
    assert d.regime == Regime.MIXED
    assert d.execution_posture in {ExecutionPosture.SELECTIVE, ExecutionPosture.DEFENSIVE}


# ─── 6. CHAOTIC quality downgrade ────────────────────────────────────────────

def test_chaotic_quality_downgrades_posture():
    inp = RegimeInputs(
        spy_change_pct=1.0,        # nominally risk-on
        qqq_change_pct=1.2,
        dxy_change_pct=-0.4,
        vix_change_pct=35.0,       # but VIX exploding → CHAOTIC quality
        headline_shock_flag=True,
        event_risk_level="HIGH",
    )
    d = classify_market_regime(inp)
    assert d.market_quality == MarketQuality.CHAOTIC
    # Posture must be degraded — not AGGRESSIVE
    assert d.execution_posture in {ExecutionPosture.DEFENSIVE, ExecutionPosture.NO_DEPLOY}


# ─── 7. Missing-input resilience ─────────────────────────────────────────────

def test_missing_inputs_do_not_raise():
    """Engine must handle an entirely empty input without error."""
    inp = RegimeInputs()
    d = classify_market_regime(inp)
    assert d.regime in Regime.__members__.values()
    assert d.market_quality in MarketQuality.__members__.values()
    assert d.execution_posture in ExecutionPosture.__members__.values()
    assert isinstance(d.drivers, list)


def test_partial_inputs_do_not_raise():
    """Partial input (only a few fields set) must produce a valid decision."""
    inp = RegimeInputs(
        gold_change_pct=1.5,
        silver_change_pct=2.0,
    )
    d = classify_market_regime(inp)
    assert d.regime is not None
    assert d.execution_posture is not None


def test_to_dict_is_serializable():
    inp = RegimeInputs(
        spy_change_pct=-1.5,
        vix_change_pct=18.0,
        us10y_change_bp=-12.0,
        gold_change_pct=0.8,
        dxy_change_pct=0.5,
    )
    d = classify_market_regime(inp)
    payload = d.to_dict()
    assert "regime" in payload
    assert "execution_posture" in payload
    assert isinstance(payload["drivers"], list)
    assert isinstance(payload["regime_confidence"], float)
