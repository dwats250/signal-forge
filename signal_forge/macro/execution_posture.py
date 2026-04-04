"""
Execution posture mapping.

Maps (Regime, MarketQuality) → ExecutionPosture.

This is the policy layer of the regime engine. It answers the question:
"Given what the market is doing and how well it's trading — what mode should we be in?"

The table below is the single place where trading aggressiveness is governed by macro regime.
"""

from __future__ import annotations

from signal_forge.macro.regime_types import ExecutionPosture, MarketQuality, Regime

# ─── Posture table ────────────────────────────────────────────────────────────

POSTURE_TABLE: dict[tuple[Regime, MarketQuality], ExecutionPosture] = {
    # ── RISK_ON ──────────────────────────────────────────────────────────────
    (Regime.RISK_ON, MarketQuality.CLEAN):   ExecutionPosture.AGGRESSIVE,
    (Regime.RISK_ON, MarketQuality.MIXED):   ExecutionPosture.SELECTIVE,
    (Regime.RISK_ON, MarketQuality.CHAOTIC): ExecutionPosture.DEFENSIVE,

    # ── RISK_OFF ─────────────────────────────────────────────────────────────
    (Regime.RISK_OFF, MarketQuality.CLEAN):   ExecutionPosture.SELECTIVE,
    (Regime.RISK_OFF, MarketQuality.MIXED):   ExecutionPosture.DEFENSIVE,
    (Regime.RISK_OFF, MarketQuality.CHAOTIC): ExecutionPosture.NO_DEPLOY,

    # ── INFLATION_SHOCK ──────────────────────────────────────────────────────
    (Regime.INFLATION_SHOCK, MarketQuality.CLEAN):   ExecutionPosture.SELECTIVE,
    (Regime.INFLATION_SHOCK, MarketQuality.MIXED):   ExecutionPosture.DEFENSIVE,
    (Regime.INFLATION_SHOCK, MarketQuality.CHAOTIC): ExecutionPosture.NO_DEPLOY,

    # ── GROWTH_SCARE ─────────────────────────────────────────────────────────
    (Regime.GROWTH_SCARE, MarketQuality.CLEAN):   ExecutionPosture.DEFENSIVE,
    (Regime.GROWTH_SCARE, MarketQuality.MIXED):   ExecutionPosture.DEFENSIVE,
    (Regime.GROWTH_SCARE, MarketQuality.CHAOTIC): ExecutionPosture.NO_DEPLOY,

    # ── COMMODITY_EXPANSION ──────────────────────────────────────────────────
    (Regime.COMMODITY_EXPANSION, MarketQuality.CLEAN):   ExecutionPosture.AGGRESSIVE,
    (Regime.COMMODITY_EXPANSION, MarketQuality.MIXED):   ExecutionPosture.SELECTIVE,
    (Regime.COMMODITY_EXPANSION, MarketQuality.CHAOTIC): ExecutionPosture.DEFENSIVE,

    # ── METALS_BID ───────────────────────────────────────────────────────────
    (Regime.METALS_BID, MarketQuality.CLEAN):   ExecutionPosture.AGGRESSIVE,
    (Regime.METALS_BID, MarketQuality.MIXED):   ExecutionPosture.SELECTIVE,
    (Regime.METALS_BID, MarketQuality.CHAOTIC): ExecutionPosture.DEFENSIVE,

    # ── LIQUIDITY_STRESS ─────────────────────────────────────────────────────
    (Regime.LIQUIDITY_STRESS, MarketQuality.CLEAN):   ExecutionPosture.NO_DEPLOY,
    (Regime.LIQUIDITY_STRESS, MarketQuality.MIXED):   ExecutionPosture.NO_DEPLOY,
    (Regime.LIQUIDITY_STRESS, MarketQuality.CHAOTIC): ExecutionPosture.NO_DEPLOY,

    # ── MIXED ────────────────────────────────────────────────────────────────
    (Regime.MIXED, MarketQuality.CLEAN):   ExecutionPosture.SELECTIVE,
    (Regime.MIXED, MarketQuality.MIXED):   ExecutionPosture.SELECTIVE,
    (Regime.MIXED, MarketQuality.CHAOTIC): ExecutionPosture.DEFENSIVE,
}

# Fallback if a combination is somehow not in the table
_FALLBACK_POSTURE = ExecutionPosture.DEFENSIVE


def get_execution_posture(regime: Regime, quality: MarketQuality) -> ExecutionPosture:
    return POSTURE_TABLE.get((regime, quality), _FALLBACK_POSTURE)
