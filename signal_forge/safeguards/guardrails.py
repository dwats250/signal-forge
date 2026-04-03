from __future__ import annotations

from typing import Any

from signal_forge.backtest.trades import Trade
from signal_forge.config import HIGH_QUALITY_MIN_SCORE, MIN_RISK_REWARD_RATIO

ALLOWED_STRUCTURES = {
    "bullish": {"call_debit", "put_credit"},
    "bearish": {"put_debit", "call_credit"},
}


def validate_trade(trade: Trade | dict[str, Any], market_context: dict[str, Any]) -> dict[str, Any]:
    normalized_trade = _coerce_trade(trade)
    reasons: list[str] = []
    score = 1.0
    approved = True

    risk_reward = normalized_trade.risk_reward_ratio
    if risk_reward < MIN_RISK_REWARD_RATIO:
        approved = False
        score -= 0.35
        reasons.append(
            f"Risk/reward below minimum: {risk_reward:.2f} < {MIN_RISK_REWARD_RATIO:.2f}"
        )
    else:
        reasons.append(f"Risk/reward passed at {risk_reward:.2f}")

    aligned_structures = ALLOWED_STRUCTURES[normalized_trade.direction]
    if normalized_trade.structure not in aligned_structures:
        approved = False
        score -= 0.3
        reasons.append("Trade structure does not match directional bias")
    else:
        reasons.append("Trade structure matches directional bias")

    volatility_regime = str(market_context.get("iv_regime", "normal")).lower()
    if volatility_regime == "high" and not normalized_trade.structure.endswith("credit"):
        score -= 0.15
        reasons.append("High IV favors credit spreads")
    elif volatility_regime == "low" and not normalized_trade.structure.endswith("debit"):
        score -= 0.15
        reasons.append("Low IV favors debit spreads")
    else:
        reasons.append("Volatility fit is acceptable")

    market_quality = str(market_context.get("market_quality", "CLEAN")).upper()
    if market_quality == "CHAOTIC":
        approved = False
        score -= 0.4
        reasons.append("Market quality is CHAOTIC, trade rejected")
    elif market_quality == "MIXED":
        if approved and score >= HIGH_QUALITY_MIN_SCORE and risk_reward >= 2.5:
            reasons.append("MIXED market allowed because setup qualifies as high quality")
        else:
            approved = False
            score -= 0.2
            reasons.append("MIXED market only allows high-quality setups")
    else:
        reasons.append("Market quality is CLEAN")

    return {
        "approved": approved and max(score, 0.0) >= 0.6,
        "score": round(max(score, 0.0), 2),
        "reasons": reasons,
    }


def _coerce_trade(trade: Trade | dict[str, Any]) -> Trade:
    if isinstance(trade, Trade):
        return trade
    return Trade(**trade)
