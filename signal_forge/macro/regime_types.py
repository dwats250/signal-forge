from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Regime(str, Enum):
    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"
    MIXED = "MIXED"
    INFLATION_SHOCK = "INFLATION_SHOCK"
    GROWTH_SCARE = "GROWTH_SCARE"
    COMMODITY_EXPANSION = "COMMODITY_EXPANSION"
    METALS_BID = "METALS_BID"
    LIQUIDITY_STRESS = "LIQUIDITY_STRESS"


class MarketQuality(str, Enum):
    CLEAN = "CLEAN"
    MIXED = "MIXED"
    CHAOTIC = "CHAOTIC"


class ExecutionPosture(str, Enum):
    AGGRESSIVE = "AGGRESSIVE"
    SELECTIVE = "SELECTIVE"
    DEFENSIVE = "DEFENSIVE"
    NO_DEPLOY = "NO_DEPLOY"


@dataclass
class RegimeInputs:
    """Cross-asset macro snapshot for regime classification. All fields optional."""

    dxy_change_pct: Optional[float] = None
    us2y_change_bp: Optional[float] = None
    us10y_change_bp: Optional[float] = None
    yield_curve_change_bp: Optional[float] = None
    vix_change_pct: Optional[float] = None
    spy_change_pct: Optional[float] = None
    qqq_change_pct: Optional[float] = None
    iwm_change_pct: Optional[float] = None
    xle_change_pct: Optional[float] = None
    gdx_change_pct: Optional[float] = None
    oil_change_pct: Optional[float] = None
    gold_change_pct: Optional[float] = None
    silver_change_pct: Optional[float] = None
    copper_change_pct: Optional[float] = None
    usd_jpy_change_pct: Optional[float] = None
    btc_change_pct: Optional[float] = None
    event_risk_level: Optional[str] = None  # "LOW", "MEDIUM", "HIGH"
    headline_shock_flag: bool = False


@dataclass
class RegimeDecision:
    """Execution-ready regime classification output."""

    regime: Regime
    regime_confidence: float  # 0.0 – 1.0
    market_quality: MarketQuality
    execution_posture: ExecutionPosture
    drivers: list[str]
    favored_themes: list[str]
    disfavored_themes: list[str]
    tailwinds: list[str]
    headwinds: list[str]
    notes: str
    raw_scores: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime.value,
            "regime_confidence": round(self.regime_confidence, 2),
            "market_quality": self.market_quality.value,
            "execution_posture": self.execution_posture.value,
            "drivers": self.drivers,
            "favored_themes": self.favored_themes,
            "disfavored_themes": self.disfavored_themes,
            "tailwinds": self.tailwinds,
            "headwinds": self.headwinds,
            "notes": self.notes,
        }
