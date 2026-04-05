from __future__ import annotations

from signal_forge.execution.models import PolicyState, StrategyType, TradeCandidate, TradePolicy
from signal_forge.macro.regime_types import MarketQuality, Regime


_DIRECTION_LONG = "LONG"
_DIRECTION_SHORT = "SHORT"
_DIRECTION_NEUTRAL = "NEUTRAL"
_DIRECTION_NONE = "NONE"

_STRUCTURE_CALL_DEBIT = "CALL_DEBIT"
_STRUCTURE_PUT_DEBIT = "PUT_DEBIT"
_STRUCTURE_CREDIT_SPREAD = "CREDIT_SPREAD"
_STRUCTURE_EQUITY = "EQUITY"
_STRUCTURE_NONE = "NONE"


def _coerce_regime(value: object) -> Regime:
    if isinstance(value, Regime):
        return value
    if isinstance(value, str):
        try:
            return Regime(value.upper())
        except ValueError:
            return Regime.MIXED
    return Regime.MIXED


def _coerce_quality(value: object) -> MarketQuality:
    if isinstance(value, MarketQuality):
        return value
    if isinstance(value, str):
        try:
            return MarketQuality(value.upper())
        except ValueError:
            return MarketQuality.MIXED
    return MarketQuality.MIXED


def _base_policy(regime: Regime, quality: MarketQuality) -> TradePolicy:
    if regime == Regime.RISK_OFF:
        return TradePolicy(
            policy_state=PolicyState.NO_TRADE,
            allowed_directions=[_DIRECTION_NONE],
            allowed_structures=[_STRUCTURE_NONE],
            position_size_pct=0.0,
            max_concurrent_trades=0,
            confidence_threshold=1.0,
            notes="Risk-off regime blocks new trades.",
        )
    if quality == MarketQuality.CLEAN and regime == Regime.RISK_ON:
        return TradePolicy(
            policy_state=PolicyState.AGGRESSIVE,
            allowed_directions=[_DIRECTION_LONG],
            allowed_structures=[_STRUCTURE_CALL_DEBIT, _STRUCTURE_CREDIT_SPREAD, _STRUCTURE_EQUITY],
            position_size_pct=1.0,
            max_concurrent_trades=4,
            confidence_threshold=0.6,
            notes="Risk-on regime with clean tape allows full-size directional deployment.",
        )
    if quality == MarketQuality.CHAOTIC:
        return TradePolicy(
            policy_state=PolicyState.DEFENSIVE,
            allowed_directions=[_DIRECTION_NEUTRAL],
            allowed_structures=[_STRUCTURE_CREDIT_SPREAD],
            position_size_pct=0.3,
            max_concurrent_trades=1,
            confidence_threshold=0.9,
            notes="Chaotic conditions force defensive posture and neutral structures only.",
        )
    return TradePolicy(
        policy_state=PolicyState.SELECTIVE,
        allowed_directions=[_DIRECTION_LONG, _DIRECTION_SHORT],
        allowed_structures=[
            _STRUCTURE_CALL_DEBIT,
            _STRUCTURE_PUT_DEBIT,
            _STRUCTURE_EQUITY,
        ],
        position_size_pct=0.6,
        max_concurrent_trades=2,
        confidence_threshold=0.75,
        notes="Mixed inputs default to reduced size and higher entry quality.",
    )


def _downgrade(policy: TradePolicy) -> TradePolicy:
    if policy.policy_state == PolicyState.AGGRESSIVE:
        return TradePolicy(
            policy_state=PolicyState.SELECTIVE,
            allowed_directions=[_DIRECTION_LONG, _DIRECTION_SHORT],
            allowed_structures=[
                _STRUCTURE_CALL_DEBIT,
                _STRUCTURE_PUT_DEBIT,
                _STRUCTURE_EQUITY,
            ],
            position_size_pct=0.6,
            max_concurrent_trades=2,
            confidence_threshold=0.75,
            notes="VIX spike downgraded posture by one level.",
        )
    if policy.policy_state == PolicyState.SELECTIVE:
        return TradePolicy(
            policy_state=PolicyState.DEFENSIVE,
            allowed_directions=[_DIRECTION_NEUTRAL],
            allowed_structures=[_STRUCTURE_CREDIT_SPREAD],
            position_size_pct=0.3,
            max_concurrent_trades=1,
            confidence_threshold=0.9,
            notes="VIX spike downgraded posture by one level.",
        )
    return TradePolicy(
        policy_state=PolicyState.NO_TRADE,
        allowed_directions=[_DIRECTION_NONE],
        allowed_structures=[_STRUCTURE_NONE],
        position_size_pct=0.0,
        max_concurrent_trades=0,
        confidence_threshold=1.0,
        notes="VIX spike escalated defensive posture to no-trade.",
    )


def resolve_trade_policy(market_context: dict[str, object] | None) -> TradePolicy:
    context = market_context or {}
    regime = _coerce_regime(context.get("regime"))
    quality = _coerce_quality(context.get("market_quality"))
    event_window_minutes = context.get("event_window_minutes")
    event_risk = bool(context.get("event_risk"))
    headline_shock_flag = bool(context.get("headline_shock_flag"))
    vix_spike = bool(context.get("vix_spike"))
    dislocation = bool(context.get("dislocation"))
    execution_posture = str(context.get("execution_posture", "")).upper()

    if execution_posture == "NO_DEPLOY":
        return TradePolicy(
            policy_state=PolicyState.NO_TRADE,
            allowed_directions=[_DIRECTION_NONE],
            allowed_structures=[_STRUCTURE_NONE],
            position_size_pct=0.0,
            max_concurrent_trades=0,
            confidence_threshold=1.0,
            notes="Macro posture already marked no-deploy.",
        )

    if event_risk and isinstance(event_window_minutes, (int, float)) and abs(event_window_minutes) <= 30:
        return TradePolicy(
            policy_state=PolicyState.NO_TRADE,
            allowed_directions=[_DIRECTION_NONE],
            allowed_structures=[_STRUCTURE_NONE],
            position_size_pct=0.0,
            max_concurrent_trades=0,
            confidence_threshold=1.0,
            notes="Scheduled event window within 30 minutes blocks new trades.",
        )

    if headline_shock_flag:
        return TradePolicy(
            policy_state=PolicyState.NO_TRADE,
            allowed_directions=[_DIRECTION_NONE],
            allowed_structures=[_STRUCTURE_NONE],
            position_size_pct=0.0,
            max_concurrent_trades=0,
            confidence_threshold=1.0,
            notes="Headline shock flag blocks discretionary deployment.",
        )

    if quality == MarketQuality.CHAOTIC and dislocation:
        return TradePolicy(
            policy_state=PolicyState.NO_TRADE,
            allowed_directions=[_DIRECTION_NONE],
            allowed_structures=[_STRUCTURE_NONE],
            position_size_pct=0.0,
            max_concurrent_trades=0,
            confidence_threshold=1.0,
            notes="Chaotic tape plus dislocation escalates to no-trade.",
        )

    policy = _base_policy(regime, quality)
    if vix_spike:
        return _downgrade(policy)
    return policy


def infer_candidate_structure(candidate: TradeCandidate) -> str:
    if candidate.strategy_type == StrategyType.EQUITY:
        return _STRUCTURE_EQUITY
    if candidate.strategy_type == StrategyType.CASH_SECURED_PUT:
        return _STRUCTURE_CREDIT_SPREAD
    if candidate.direction.value == "bullish":
        return _STRUCTURE_CALL_DEBIT
    return _STRUCTURE_PUT_DEBIT


def _candidate_direction(candidate: TradeCandidate) -> str:
    if candidate.direction.value == "bullish":
        return _DIRECTION_LONG
    return _DIRECTION_SHORT


def _stop_distance_pct(candidate: TradeCandidate) -> float:
    entry = candidate.entry_trigger.price
    return abs(entry - candidate.stop_level) / entry


def filter_trade_candidate(
    candidate: TradeCandidate,
    policy: TradePolicy,
    *,
    active_trade_count: int,
) -> tuple[bool, str]:
    direction = _candidate_direction(candidate)
    if direction not in policy.allowed_directions:
        return False, f"direction {direction} blocked by {policy.policy_state.value} policy"

    structure = infer_candidate_structure(candidate)
    if structure not in policy.allowed_structures:
        return False, f"structure {structure} blocked by {policy.policy_state.value} policy"

    if candidate.score < policy.confidence_threshold:
        return False, "candidate score below policy confidence threshold"

    stop_distance = abs(candidate.entry_trigger.price - candidate.stop_level)
    target_distance = abs(candidate.target_level - candidate.entry_trigger.price)
    if stop_distance <= 0 or target_distance / stop_distance < 2:
        return False, "candidate fails minimum 2:1 reward-to-risk constraint"

    if _stop_distance_pct(candidate) < 0.01:
        atr = candidate.atr
        if atr is None or stop_distance < 0.5 * atr:
            return False, "candidate fails minimum stop distance constraint"

    if not candidate.ema_aligned:
        return False, "candidate fails EMA alignment constraint"

    if candidate.averaging_down:
        return False, "averaging down is disallowed by policy"

    return True, f"{policy.policy_state.value} policy allows candidate"
