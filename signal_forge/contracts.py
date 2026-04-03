from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


VALID_STATES = {"bullish", "bearish", "neutral", "blocked"}
VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_MARKET_STATES = {"CHOP", "TREND", "EXPANSION", "MIXED"}
VALID_VOLATILITY_REGIMES = {"LOW", "NORMAL", "HIGH"}
VALID_EXPRESSIONS = {"CREDIT_BULL", "CREDIT_BEAR", "DEBIT_BULL", "DEBIT_BEAR"}
VALID_SAFEGUARD_DECISIONS = {"TRADE", "NO_TRADE", "OVERRIDE"}
VALID_OVERRIDE_REASONS = {
    "VOL_STRUCTURE_EDGE",
    "RANGE_COMPRESSION",
    "PINNING",
    "SKEW",
    "EVENT_DISLOCATION",
}


@dataclass(slots=True)
class AgentOutput:
    domain: str
    state: str
    confidence: str
    key_factors: list[str]
    time_horizon: str = "swing"
    special_flags: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.state not in VALID_STATES:
            raise ValueError(f"Unsupported state: {self.state}")
        if self.confidence not in VALID_CONFIDENCE:
            raise ValueError(f"Unsupported confidence: {self.confidence}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Thesis:
    thesis_id: str
    direction: str
    confidence: str
    drivers: list[str]
    invalidators: list[str]
    agent_outputs: dict[str, AgentOutput]

    @classmethod
    def create(
        cls,
        direction: str,
        confidence: str,
        drivers: list[str],
        invalidators: list[str],
        agent_outputs: dict[str, AgentOutput],
    ) -> "Thesis":
        return cls(
            thesis_id=str(uuid4()),
            direction=direction,
            confidence=confidence,
            drivers=drivers,
            invalidators=invalidators,
            agent_outputs=agent_outputs,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["agent_outputs"] = {
            name: output.to_dict() for name, output in self.agent_outputs.items()
        }
        return data


@dataclass(slots=True)
class ConflictResult:
    deployment_allowed: bool
    risk_level: str
    constraints: list[str]
    notes: str
    conflict_types: list[str] = field(default_factory=list)
    dominant_domain: str | None = None
    suppressed_domains: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExecutionInput:
    thesis: Thesis
    conflict: ConflictResult
    market_state: str | None = None
    volatility_regime: str | None = None
    expression_type: str | None = None
    confidence_score: int | None = None
    catalyst_flag: bool = False
    safeguard: "SafeguardResult | None" = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "thesis": self.thesis.to_dict(),
            "conflict": self.conflict.to_dict(),
        }
        if self.market_state is not None:
            payload["market_state"] = self.market_state
        if self.volatility_regime is not None:
            payload["volatility_regime"] = self.volatility_regime
        if self.expression_type is not None:
            payload["expression_type"] = self.expression_type
        if self.confidence_score is not None:
            payload["confidence_score"] = self.confidence_score
        payload["catalyst_flag"] = self.catalyst_flag
        if self.safeguard is not None:
            payload["safeguard"] = self.safeguard.to_dict()
        return payload


@dataclass(slots=True)
class SafeguardInput:
    market_state: str
    volatility_regime: str
    expression_type: str
    confidence_score: int
    catalyst_flag: bool
    override_flag: bool = False
    override_reason: str | None = None

    def __post_init__(self) -> None:
        if self.market_state not in VALID_MARKET_STATES:
            raise ValueError(f"Unsupported market state: {self.market_state}")
        if self.volatility_regime not in VALID_VOLATILITY_REGIMES:
            raise ValueError(f"Unsupported volatility regime: {self.volatility_regime}")
        if self.expression_type not in VALID_EXPRESSIONS:
            raise ValueError(f"Unsupported expression type: {self.expression_type}")
        if not 0 <= self.confidence_score <= 100:
            raise ValueError("confidence_score must be between 0 and 100")
        if self.override_flag:
            if self.override_reason not in VALID_OVERRIDE_REASONS:
                raise ValueError("override_reason must be a supported override code")
        elif self.override_reason is not None:
            raise ValueError("override_reason requires override_flag=True")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SafeguardResult:
    decision: str
    allowed: bool
    reason: str
    confidence: int
    blocked_expressions: list[str] = field(default_factory=list)
    posture: str = "WAIT"
    override_flag: bool = False
    override_reason: str | None = None

    def __post_init__(self) -> None:
        if self.decision not in VALID_SAFEGUARD_DECISIONS:
            raise ValueError(f"Unsupported safeguard decision: {self.decision}")
        if not 0 <= self.confidence <= 100:
            raise ValueError("confidence must be between 0 and 100")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TradeProxy:
    entry_price: float
    stop_level: float
    target_level: float
    time_window: int
    max_loss: float
    max_gain: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BacktestTradeResult:
    expression_type: str
    outcome: str
    pnl: float
    return_pct: float
    bars_held: int
    no_trade: bool
    reason: str
    proxy: TradeProxy

    def __post_init__(self) -> None:
        if self.expression_type not in VALID_EXPRESSIONS:
            raise ValueError(f"Unsupported expression type: {self.expression_type}")
        if self.outcome not in {"WIN", "LOSS", "NO_TRADE"}:
            raise ValueError(f"Unsupported trade outcome: {self.outcome}")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["proxy"] = self.proxy.to_dict()
        return payload


@dataclass(slots=True)
class BacktestSummary:
    trades: int
    wins: int
    losses: int
    no_trade_count: int
    win_rate: float
    expectancy: float
    max_drawdown: float
    profit_factor: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BacktestResult:
    summary: BacktestSummary
    trades: list[BacktestTradeResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary.to_dict(),
            "trades": [trade.to_dict() for trade in self.trades],
        }


@dataclass(slots=True)
class LogEntry:
    timestamp: str
    thesis_id: str
    decision: str
    notes: str

    @classmethod
    def create(cls, thesis_id: str, decision: str, notes: str) -> "LogEntry":
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(),
            thesis_id=thesis_id,
            decision=decision,
            notes=notes,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DislocationReading:
    futures_symbol: str
    etf_symbol: str
    futures_pct_change: float
    etf_pct_change: float

    @property
    def divergence(self) -> float:
        return abs(self.futures_pct_change - self.etf_pct_change)

    def to_dict(self) -> dict[str, Any]:
        return {
            "futures_symbol": self.futures_symbol,
            "etf_symbol": self.etf_symbol,
            "futures_pct_change": self.futures_pct_change,
            "etf_pct_change": self.etf_pct_change,
            "divergence": self.divergence,
        }
