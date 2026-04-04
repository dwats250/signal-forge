"""
Weighted scoring rules for each market regime.

Each rule function receives RegimeInputs and returns a tuple of:
  (score_delta: float, label: str)

The label is a human-readable string used to build the `drivers` list.
Rules are additive — multiple rules can fire for the same regime.
Missing inputs are handled by returning 0 for that rule (None-safe throughout).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from signal_forge.macro.regime_types import RegimeInputs

# ─── helpers ─────────────────────────────────────────────────────────────────

def _v(val: float | None, default: float = 0.0) -> float:
    return val if val is not None else default


# ─── RISK_ON ─────────────────────────────────────────────────────────────────

def score_risk_on(inp: "RegimeInputs") -> list[tuple[float, str]]:
    hits: list[tuple[float, str]] = []

    if _v(inp.dxy_change_pct) < -0.3:
        hits.append((15, "DXY weakening — dollar headwind removed"))
    if _v(inp.spy_change_pct) > 0.5:
        hits.append((20, "SPY bid — broad equity strength"))
    if _v(inp.qqq_change_pct) > 0.5:
        hits.append((12, "QQQ bid — growth/tech leadership"))
    if _v(inp.iwm_change_pct) > 0.3:
        hits.append((10, "IWM bid — small-cap risk appetite"))
    if _v(inp.vix_change_pct) < -5:
        hits.append((15, "VIX compressing — vol sellers active"))
    if -8 < _v(inp.us10y_change_bp) < 15:
        hits.append((5, "10Y yields stable — growth without rate fear"))
    if _v(inp.gold_change_pct) < 0.2 and _v(inp.spy_change_pct) > 0:
        hits.append((5, "Gold flat/down while equities rally — no safety bid"))
    if _v(inp.usd_jpy_change_pct) > 0.3:
        hits.append((8, "USD/JPY rising — carry trade active"))

    return hits


# ─── RISK_OFF ────────────────────────────────────────────────────────────────

def score_risk_off(inp: "RegimeInputs") -> list[tuple[float, str]]:
    hits: list[tuple[float, str]] = []

    if _v(inp.dxy_change_pct) > 0.3:
        hits.append((12, "DXY bid — dollar as safety"))
    if _v(inp.spy_change_pct) < -0.5:
        hits.append((20, "SPY selling — broad risk-off"))
    if _v(inp.qqq_change_pct) < -0.5:
        hits.append((12, "QQQ selling — growth under pressure"))
    if _v(inp.vix_change_pct) > 10:
        hits.append((20, "VIX spiking — fear elevated"))
    if _v(inp.us10y_change_bp) < -8:
        hits.append((15, "10Y yields falling — flight to treasuries"))
    if _v(inp.gold_change_pct) > 0.5:
        hits.append((10, "Gold bid — safety demand"))
    if _v(inp.usd_jpy_change_pct) < -0.5:
        hits.append((10, "USD/JPY falling — yen safety bid, carry unwind"))
    if _v(inp.btc_change_pct) < -3 and _v(inp.spy_change_pct) < 0:
        hits.append((8, "BTC + equities down — broad risk liquidation"))

    return hits


# ─── INFLATION_SHOCK ─────────────────────────────────────────────────────────

def score_inflation_shock(inp: "RegimeInputs") -> list[tuple[float, str]]:
    hits: list[tuple[float, str]] = []

    if _v(inp.oil_change_pct) > 2.0:
        hits.append((22, "Oil surging — supply/demand shock"))
    if _v(inp.us2y_change_bp) > 10:
        hits.append((15, "2Y yields rising — near-term rate pressure"))
    if _v(inp.us10y_change_bp) > 10:
        hits.append((15, "10Y yields rising — inflation premium building"))
    if _v(inp.dxy_change_pct) > 0.4:
        hits.append((10, "DXY bid — hawkish dollar"))
    if _v(inp.spy_change_pct) < 0 and _v(inp.oil_change_pct) > 1:
        hits.append((12, "Equities weak while oil rises — stagflation concern"))
    if _v(inp.gold_change_pct) > 0.5 and _v(inp.us10y_change_bp) > 5:
        hits.append((8, "Gold + yields rising — real inflation hedge bid"))
    if _v(inp.copper_change_pct) > 1.5:
        hits.append((8, "Copper rising — demand-driven inflation signal"))

    return hits


# ─── GROWTH_SCARE ─────────────────────────────────────────────────────────────

def score_growth_scare(inp: "RegimeInputs") -> list[tuple[float, str]]:
    hits: list[tuple[float, str]] = []

    if _v(inp.spy_change_pct) < -1.0:
        hits.append((20, "SPY hard selling — growth concern"))
    if _v(inp.qqq_change_pct) < -1.0:
        hits.append((15, "QQQ under pressure — tech/growth repricing"))
    if _v(inp.us10y_change_bp) < -8:
        hits.append((15, "10Y falling on fear — recession hedges active"))
    if _v(inp.dxy_change_pct) > 0.3:
        hits.append((10, "DXY strong — dollar safety bid"))
    if _v(inp.oil_change_pct) < -1.5:
        hits.append((12, "Oil selling — demand destruction signal"))
    if _v(inp.copper_change_pct) < -1.0:
        hits.append((12, "Copper selling — industrial slowdown signal"))
    if _v(inp.iwm_change_pct) < -1.5:
        hits.append((10, "IWM lagging — small-cap growth sensitivity"))
    if _v(inp.yield_curve_change_bp) < -5:
        hits.append((8, "Yield curve flattening/inverting — recession signal"))

    return hits


# ─── COMMODITY_EXPANSION ─────────────────────────────────────────────────────

def score_commodity_expansion(inp: "RegimeInputs") -> list[tuple[float, str]]:
    hits: list[tuple[float, str]] = []

    if _v(inp.oil_change_pct) > 1.5:
        hits.append((20, "Oil strong — energy demand/supply dynamic"))
    if _v(inp.copper_change_pct) > 1.0:
        hits.append((20, "Copper strong — industrial expansion demand"))
    if _v(inp.xle_change_pct) > 1.0:
        hits.append((15, "XLE bid — energy equity leadership"))
    if _v(inp.gold_change_pct) > 0.5:
        hits.append((8, "Gold participating — commodity complex bid"))
    if _v(inp.silver_change_pct) > 1.0:
        hits.append((10, "Silver bid — industrial + precious metal demand"))
    if _v(inp.dxy_change_pct) < -0.2:
        hits.append((10, "DXY weakening — dollar commodity tailwind"))
    # Distinguishing from inflation shock: equities not collapsing
    if _v(inp.spy_change_pct) > -0.5:
        hits.append((7, "Equities not collapsing — expansion not stagflation"))

    return hits


# ─── METALS_BID ──────────────────────────────────────────────────────────────

def score_metals_bid(inp: "RegimeInputs") -> list[tuple[float, str]]:
    hits: list[tuple[float, str]] = []

    if _v(inp.gold_change_pct) > 1.0:
        hits.append((25, "Gold surging — metals leadership"))
    if _v(inp.gdx_change_pct) > 1.0:
        hits.append((20, "GDX bid — miners amplifying gold move"))
    if _v(inp.silver_change_pct) > 1.0:
        hits.append((15, "Silver bid — precious metals complex active"))
    if _v(inp.dxy_change_pct) < -0.3:
        hits.append((12, "DXY weak — dollar tailwind for metals"))
    if _v(inp.us2y_change_bp) < 0:
        hits.append((8, "2Y yields flat/falling — real rate tailwind for gold"))
    if _v(inp.us10y_change_bp) < 0:
        hits.append((8, "10Y yields flat/falling — gold inverse correlation firing"))
    if _v(inp.copper_change_pct) > 0.5:
        hits.append((5, "Copper also bid — broad metals participation"))

    return hits


# ─── LIQUIDITY_STRESS ────────────────────────────────────────────────────────

def score_liquidity_stress(inp: "RegimeInputs") -> list[tuple[float, str]]:
    hits: list[tuple[float, str]] = []

    if _v(inp.vix_change_pct) > 20:
        hits.append((25, "VIX spike >20% — acute stress event"))
    if inp.headline_shock_flag:
        hits.append((20, "Headline shock active — event-driven dislocation"))
    if inp.event_risk_level == "HIGH":
        hits.append((15, "Event risk HIGH — binary outcome period"))
    if _v(inp.spy_change_pct) < -2.0:
        hits.append((20, "SPY -2%+ — forced selling / margin pressure"))
    if _v(inp.us2y_change_bp) > 15:
        hits.append((15, "2Y yields spiking — funding stress signal"))
    if _v(inp.btc_change_pct) < -5.0:
        hits.append((15, "BTC dumping — risk-off liquidity drain"))
    if _v(inp.gold_change_pct) < 0 and _v(inp.spy_change_pct) < -2:
        hits.append((10, "Gold not holding — everything-sold liquidation"))

    return hits


# ─── MIXED ────────────────────────────────────────────────────────────────────

def score_mixed(inp: "RegimeInputs") -> list[tuple[float, str]]:
    """
    MIXED scores high when cross-asset signals disagree or lack clear directional alignment.
    Base score ensures it can win when nothing else is clearly dominant.
    """
    hits: list[tuple[float, str]] = []

    # Baseline: MIXED always gets some weight
    hits.append((10, "No dominant regime signal — baseline MIXED"))

    # Contradictory equity / bond signals
    if _v(inp.spy_change_pct) > 0.5 and _v(inp.us10y_change_bp) > 10:
        hits.append((12, "Equities up + yields rising — conflicting growth/rate signal"))
    if _v(inp.spy_change_pct) < -0.5 and _v(inp.us10y_change_bp) > 5:
        hits.append((12, "Equities down + yields rising — stagflation signal"))

    # Dollar / equity divergence
    if _v(inp.dxy_change_pct) > 0.5 and _v(inp.spy_change_pct) > 0.5:
        hits.append((10, "Dollar + equities both rising — unstable combination"))

    # Commodity contradiction
    if _v(inp.oil_change_pct) > 1 and _v(inp.gold_change_pct) > 1 and _v(inp.spy_change_pct) > 0.5:
        hits.append((10, "Oil + gold + equities all rising — cross-asset noise"))

    # Small-cap vs large-cap divergence
    if inp.spy_change_pct is not None and inp.iwm_change_pct is not None:
        spread = abs(_v(inp.spy_change_pct) - _v(inp.iwm_change_pct))
        if spread > 1.0:
            hits.append((10, f"SPY/IWM spread {spread:.1f}% — bifurcated equity market"))

    return hits


# ─── Registry ────────────────────────────────────────────────────────────────

REGIME_SCORERS = {
    "RISK_ON": score_risk_on,
    "RISK_OFF": score_risk_off,
    "INFLATION_SHOCK": score_inflation_shock,
    "GROWTH_SCARE": score_growth_scare,
    "COMMODITY_EXPANSION": score_commodity_expansion,
    "METALS_BID": score_metals_bid,
    "LIQUIDITY_STRESS": score_liquidity_stress,
    "MIXED": score_mixed,
}
