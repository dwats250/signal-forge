from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


VALID_STATES = {"bullish", "bearish", "neutral", "blocked"}
VALID_CONFIDENCE = {"high", "medium", "low"}


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "thesis": self.thesis.to_dict(),
            "conflict": self.conflict.to_dict(),
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
