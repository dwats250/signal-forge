from __future__ import annotations

from math import floor

from signal_forge.execution.models import (
    ExecutionPolicy,
    StrategyType,
    TradeCandidate,
    TradeTicket,
)


def _normalize_risk_percent(risk_percent: float) -> float:
    if risk_percent <= 0:
        raise ValueError("risk_percent must be positive")
    if risk_percent < 1:
        return risk_percent
    if risk_percent <= 100:
        return risk_percent / 100
    raise ValueError("risk_percent must be a fraction or percentage")


def _equity_position_size(candidate: TradeCandidate, risk_budget: float) -> tuple[int, float]:
    stop_distance = abs(candidate.entry_trigger.price - candidate.stop_level)
    if stop_distance <= 0:
        raise ValueError("stop distance must be positive")
    position_size = floor(risk_budget / stop_distance)
    if position_size <= 0:
        raise ValueError("risk budget is too small for the stop distance")
    max_risk = round(position_size * stop_distance, 2)
    return position_size, max_risk


def _option_max_loss(candidate: TradeCandidate, policy: ExecutionPolicy) -> tuple[int, float, str]:
    structure = candidate.option_structure
    if structure is None:
        raise ValueError("option_structure is required")
    if structure.days_to_expiry < policy.min_option_dte:
        raise ValueError("option trade fails minimum DTE policy")
    if structure.open_interest < policy.min_open_interest:
        raise ValueError("option trade fails minimum open interest policy")
    if structure.spread_pct > policy.max_spread_pct:
        raise ValueError("option trade fails maximum spread policy")

    if candidate.strategy_type == StrategyType.DEBIT_SPREAD:
        if structure.net_debit is None:
            raise ValueError("debit spreads require net_debit")
        per_contract_loss = structure.net_debit
    elif candidate.strategy_type == StrategyType.CASH_SECURED_PUT:
        if structure.strike is None or structure.premium is None:
            raise ValueError("cash-secured puts require strike and premium")
        per_contract_loss = (structure.strike - structure.premium) * 100
    else:
        raise ValueError("unsupported option strategy")

    if per_contract_loss <= 0:
        raise ValueError("option max loss must be positive")
    return structure.contracts, round(per_contract_loss * structure.contracts, 2), structure.expiry


def calculate_trade_ticket(
    candidate: TradeCandidate,
    *,
    account_size: float,
    risk_percent: float,
    policy: ExecutionPolicy | None = None,
) -> TradeTicket:
    if account_size <= 0:
        raise ValueError("account_size must be positive")

    normalized_risk = _normalize_risk_percent(risk_percent)
    risk_budget = round(account_size * normalized_risk, 2)
    if risk_budget <= 0:
        raise ValueError("risk budget must be positive")

    stop_distance = abs(candidate.entry_trigger.price - candidate.stop_level)
    if stop_distance <= 0:
        raise ValueError("stop distance must be positive")
    r_multiple = round(abs(candidate.target_level - candidate.entry_trigger.price) / stop_distance, 4)
    if r_multiple <= 0:
        raise ValueError("R multiple must be positive")

    if candidate.strategy_type == StrategyType.EQUITY:
        position_size, max_risk = _equity_position_size(candidate, risk_budget)
        expiry = None
    else:
        effective_policy = policy or ExecutionPolicy()
        contracts, max_loss, expiry = _option_max_loss(candidate, effective_policy)
        per_contract_loss = max_loss / contracts
        position_size = floor(risk_budget / per_contract_loss)
        if position_size <= 0:
            raise ValueError("risk budget is too small for the option structure")
        max_risk = round(per_contract_loss * position_size, 2)

    return TradeTicket(
        entry_price=candidate.entry_trigger.price,
        stop_price=candidate.stop_level,
        position_size=position_size,
        max_risk=max_risk,
        R_multiple=r_multiple,
        expiry=expiry,
    )
