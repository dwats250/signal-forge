from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ScoreCard:
    persistence: int        # 1-5
    crowding: int           # 1-5 (lower = better)
    clarity: int            # 1-5
    regime_fit: int         # 1-5
    exploitability: int     # 1-5
    total_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "persistence": self.persistence,
            "crowding": self.crowding,
            "clarity": self.clarity,
            "regime_fit": self.regime_fit,
            "exploitability": self.exploitability,
            "total_score": self.total_score,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ScoreCard":
        return cls(
            persistence=d["persistence"],
            crowding=d["crowding"],
            clarity=d["clarity"],
            regime_fit=d["regime_fit"],
            exploitability=d["exploitability"],
            total_score=d.get("total_score", 0.0),
        )


@dataclass
class EdgeComponent:
    name: str
    category: str
    trigger: str
    confirmation: str
    regime: str
    edge_source: str
    execution: str
    invalidation: str
    notes: str
    score: Optional[ScoreCard] = None

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "category": self.category,
            "trigger": self.trigger,
            "confirmation": self.confirmation,
            "regime": self.regime,
            "edge_source": self.edge_source,
            "execution": self.execution,
            "invalidation": self.invalidation,
            "notes": self.notes,
        }
        if self.score is not None:
            d["score"] = self.score.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "EdgeComponent":
        score = ScoreCard.from_dict(d["score"]) if "score" in d else None
        return cls(
            name=d["name"],
            category=d["category"],
            trigger=d["trigger"],
            confirmation=d["confirmation"],
            regime=d["regime"],
            edge_source=d["edge_source"],
            execution=d["execution"],
            invalidation=d["invalidation"],
            notes=d["notes"],
            score=score,
        )


@dataclass
class StrategyEntry:
    name: str
    description: str
    components: List[EdgeComponent] = field(default_factory=list)
    score: Optional[ScoreCard] = None

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "description": self.description,
            "components": [c.to_dict() for c in self.components],
        }
        if self.score is not None:
            d["score"] = self.score.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "StrategyEntry":
        score = ScoreCard.from_dict(d["score"]) if "score" in d else None
        return cls(
            name=d["name"],
            description=d["description"],
            components=[EdgeComponent.from_dict(c) for c in d.get("components", [])],
            score=score,
        )
