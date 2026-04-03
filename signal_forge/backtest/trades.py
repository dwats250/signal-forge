from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from signal_forge.config import DEFAULT_TIMEOUT_BARS

VALID_DIRECTIONS = {"bullish", "bearish"}
VALID_STRUCTURES = {"call_debit", "put_debit", "call_credit", "put_credit"}


@dataclass(slots=True)
class Trade:
    symbol: str
    direction: str
    structure: str
    entry_price: float
    stop: float
    target: float
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    timeout_bars: int = DEFAULT_TIMEOUT_BARS

    def __post_init__(self) -> None:
        if self.direction not in VALID_DIRECTIONS:
            raise ValueError(f"Unsupported direction: {self.direction}")
        if self.structure not in VALID_STRUCTURES:
            raise ValueError(f"Unsupported structure: {self.structure}")
        if self.entry_price <= 0:
            raise ValueError("entry_price must be positive")
        if self.timeout_bars <= 0:
            raise ValueError("timeout_bars must be positive")

    @property
    def risk(self) -> float:
        return abs(self.entry_price - self.stop)

    @property
    def reward(self) -> float:
        return abs(self.target - self.entry_price)

    @property
    def risk_reward_ratio(self) -> float:
        if self.risk == 0:
            return 0.0
        return self.reward / self.risk

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
