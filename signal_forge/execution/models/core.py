from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TradeState(Enum):
    CREATED = 1
    MARKET_APPROVED = 2
    SETUP_APPROVED = 3
    RISK_APPROVED = 4
    READY = 5
    EXECUTED = 6
    CLOSED = 7


class StrategyType(str, Enum):
    EQUITY = "equity"
    DEBIT_SPREAD = "debit_spread"
    CASH_SECURED_PUT = "cash_secured_put"


class TradeDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class PolicyState(str, Enum):
    AGGRESSIVE = "AGGRESSIVE"
    SELECTIVE = "SELECTIVE"
    DEFENSIVE = "DEFENSIVE"
    NO_TRADE = "NO_TRADE"


class ReviewDeviationType(str, Enum):
    NONE = "none"
    ENTRY = "entry"
    STOP = "stop"
    EXIT = "exit"
    MULTIPLE = "multiple"
    DISCIPLINED_LOSS = "disciplined_loss"


class FillStatus(str, Enum):
    FILLED = "filled"
    PARTIAL = "partial"
    RETRY = "retry"


@dataclass(slots=True)
class EntryTrigger:
    trigger_type: str
    price: float
    time_in_force: str = "DAY"

    def __post_init__(self) -> None:
        if not self.trigger_type:
            raise ValueError("trigger_type is required")
        if self.price <= 0:
            raise ValueError("entry trigger price must be positive")
        if not self.time_in_force:
            raise ValueError("time_in_force is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OptionStructure:
    expiry: str
    days_to_expiry: int
    contracts: int
    open_interest: int
    spread_pct: float
    net_debit: float | None = None
    strike: float | None = None
    premium: float | None = None

    def __post_init__(self) -> None:
        if not self.expiry:
            raise ValueError("expiry is required for option structures")
        if self.days_to_expiry <= 0:
            raise ValueError("days_to_expiry must be positive")
        if self.contracts <= 0:
            raise ValueError("contracts must be positive")
        if self.open_interest < 0:
            raise ValueError("open_interest cannot be negative")
        if self.spread_pct < 0:
            raise ValueError("spread_pct cannot be negative")
        if self.net_debit is not None and self.net_debit <= 0:
            raise ValueError("net_debit must be positive when provided")
        if self.strike is not None and self.strike <= 0:
            raise ValueError("strike must be positive when provided")
        if self.premium is not None and self.premium < 0:
            raise ValueError("premium cannot be negative when provided")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TradePolicy:
    policy_state: PolicyState
    allowed_directions: list[str]
    allowed_structures: list[str]
    position_size_pct: float
    max_concurrent_trades: int
    confidence_threshold: float
    notes: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.position_size_pct <= 1.0:
            raise ValueError("position_size_pct must be between 0.0 and 1.0")
        if self.max_concurrent_trades < 0:
            raise ValueError("max_concurrent_trades cannot be negative")
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0.0 and 1.0")
        if not self.notes:
            raise ValueError("notes is required")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["policy_state"] = self.policy_state.value
        return payload


@dataclass(slots=True)
class TradeCandidate:
    symbol: str
    strategy_type: StrategyType
    direction: TradeDirection
    entry_trigger: EntryTrigger
    stop_level: float
    target_level: float
    option_structure: OptionStructure | None = None
    score: float = 1.0
    ema_aligned: bool = True
    atr: float | None = None
    averaging_down: bool = False
    trade_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol is required")
        if self.stop_level <= 0 or self.target_level <= 0:
            raise ValueError("stop_level and target_level must be positive")
        if self.option_structure is None and self.strategy_type in {
            StrategyType.DEBIT_SPREAD,
            StrategyType.CASH_SECURED_PUT,
        }:
            raise ValueError("option_structure is required for option strategies")
        if self.option_structure is not None and self.strategy_type == StrategyType.EQUITY:
            raise ValueError("equity trades cannot include option_structure")
        if self.strategy_type == StrategyType.CASH_SECURED_PUT and self.direction != TradeDirection.BULLISH:
            raise ValueError("cash_secured_put trades must be bullish")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be between 0.0 and 1.0")
        if self.atr is not None and self.atr <= 0:
            raise ValueError("atr must be positive when provided")

        entry_price = self.entry_trigger.price
        if self.direction == TradeDirection.BULLISH:
            if not self.stop_level < entry_price < self.target_level:
                raise ValueError("bullish trades require stop < entry < target")
        else:
            if not self.target_level < entry_price < self.stop_level:
                raise ValueError("bearish trades require target < entry < stop")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["strategy_type"] = self.strategy_type.value
        payload["direction"] = self.direction.value
        if self.option_structure is not None:
            payload["option_structure"] = self.option_structure.to_dict()
        return payload


@dataclass(slots=True)
class TradeTicket:
    entry_price: float
    stop_price: float
    position_size: int
    max_risk: float
    R_multiple: float
    expiry: str | None = None

    def __post_init__(self) -> None:
        if self.entry_price <= 0 or self.stop_price <= 0:
            raise ValueError("ticket entry and stop must be positive")
        if self.position_size <= 0:
            raise ValueError("position_size must be positive")
        if self.max_risk <= 0:
            raise ValueError("max_risk must be positive")
        if self.R_multiple <= 0:
            raise ValueError("R_multiple must be positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ReviewResult:
    followed_entry: bool
    followed_stop: bool
    followed_exit: bool
    deviation_type: ReviewDeviationType
    result_R: float
    reviewed_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not isfinite(self.result_R):
            raise ValueError("result_R must be finite")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["deviation_type"] = self.deviation_type.value
        return payload


@dataclass(slots=True)
class PolicyChange:
    timestamp: str
    field: str
    previous_value: Any
    new_value: Any
    reason: str
    review_window: int

    def __post_init__(self) -> None:
        if not self.field:
            raise ValueError("field is required")
        if not self.reason:
            raise ValueError("reason is required")
        if self.review_window <= 0:
            raise ValueError("review_window must be positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExecutionPolicy:
    min_option_dte: int = 21
    min_open_interest: int = 250
    max_spread_pct: float = 0.1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TradeRecord:
    trade_id: str
    state: TradeState
    candidate: TradeCandidate
    market_result: dict[str, Any] | None = None
    trade_policy: dict[str, Any] | None = None
    setup_result: dict[str, Any] | None = None
    ticket: TradeTicket | None = None
    review_result: ReviewResult | None = None
    rejection_reason: str | None = None
    execution_price: float | None = None
    exit_price: float | None = None
    closure_reason: str | None = None
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "trade_id": self.trade_id,
            "state": self.state.name,
            "candidate": self.candidate.to_dict(),
            "updated_at": self.updated_at,
        }
        if self.trade_policy is not None:
            payload["trade_policy"] = self.trade_policy
        if self.market_result is not None:
            payload["market_result"] = self.market_result
        if self.setup_result is not None:
            payload["setup_result"] = self.setup_result
        if self.ticket is not None:
            payload["ticket"] = self.ticket.to_dict()
        if self.review_result is not None:
            payload["review_result"] = self.review_result.to_dict()
        if self.rejection_reason is not None:
            payload["rejection_reason"] = self.rejection_reason
        if self.execution_price is not None:
            payload["execution_price"] = self.execution_price
        if self.exit_price is not None:
            payload["exit_price"] = self.exit_price
        if self.closure_reason is not None:
            payload["closure_reason"] = self.closure_reason
        return payload
