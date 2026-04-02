from __future__ import annotations

from dataclasses import dataclass

from signal_forge.contracts import DislocationReading


DEFAULT_CLEAN_THRESHOLD = 1.0
DEFAULT_DISLOCATION_THRESHOLD = 3.0


@dataclass(slots=True, frozen=True)
class DislocationClassification:
    signal: str
    pair: str
    futures_symbol: str
    etf_symbol: str
    direction_relation: str
    leader: str
    explanation: str
    divergence: float
    divergence_band: str

    def to_dict(self) -> dict[str, str | float]:
        return {
            "signal": self.signal,
            "pair": self.pair,
            "futures_symbol": self.futures_symbol,
            "etf_symbol": self.etf_symbol,
            "direction_relation": self.direction_relation,
            "leader": self.leader,
            "divergence": round(self.divergence, 2),
            "divergence_band": self.divergence_band,
            "explanation": self.explanation,
        }


def classify_dislocation(
    reading: DislocationReading,
    *,
    clean_threshold: float = DEFAULT_CLEAN_THRESHOLD,
    dislocation_threshold: float = DEFAULT_DISLOCATION_THRESHOLD,
) -> DislocationClassification:
    divergence = reading.divergence
    pair = f"{reading.futures_symbol}/{reading.etf_symbol}"
    same_direction = reading.futures_pct_change * reading.etf_pct_change > 0
    direction_relation = (
        "same_direction" if same_direction else "opposite_direction"
    )
    leader = _leader(
        reading.futures_pct_change,
        reading.etf_pct_change,
    )
    divergence_band = _divergence_band(
        divergence,
        clean_threshold=clean_threshold,
        dislocation_threshold=dislocation_threshold,
    )
    explanation = _explanation(direction_relation, leader, divergence_band)

    if not same_direction:
        return DislocationClassification(
            signal="DISLOCATION",
            pair=pair,
            futures_symbol=reading.futures_symbol,
            etf_symbol=reading.etf_symbol,
            direction_relation=direction_relation,
            leader=leader,
            explanation=explanation,
            divergence=divergence,
            divergence_band=divergence_band,
        )

    if divergence < clean_threshold:
        return DislocationClassification(
            signal="CLEAN",
            pair=pair,
            futures_symbol=reading.futures_symbol,
            etf_symbol=reading.etf_symbol,
            direction_relation=direction_relation,
            leader=leader,
            explanation=explanation,
            divergence=divergence,
            divergence_band=divergence_band,
        )

    if divergence <= dislocation_threshold:
        return DislocationClassification(
            signal="MIXED",
            pair=pair,
            futures_symbol=reading.futures_symbol,
            etf_symbol=reading.etf_symbol,
            direction_relation=direction_relation,
            leader=leader,
            explanation=explanation,
            divergence=divergence,
            divergence_band=divergence_band,
        )

    return DislocationClassification(
        signal="DISLOCATION",
        pair=pair,
        futures_symbol=reading.futures_symbol,
        etf_symbol=reading.etf_symbol,
        direction_relation=direction_relation,
        leader=leader,
        explanation=explanation,
        divergence=divergence,
        divergence_band=divergence_band,
    )


@dataclass(slots=True)
class DislocationEngine:
    clean_threshold: float = DEFAULT_CLEAN_THRESHOLD
    dislocation_threshold: float = DEFAULT_DISLOCATION_THRESHOLD

    def evaluate(
        self,
        futures_symbol: str,
        etf_symbol: str,
        futures_pct: float,
        etf_pct: float,
    ) -> DislocationClassification:
        reading = DislocationReading(
            futures_symbol=futures_symbol,
            etf_symbol=etf_symbol,
            futures_pct_change=futures_pct,
            etf_pct_change=etf_pct,
        )
        return classify_dislocation(
            reading,
            clean_threshold=self.clean_threshold,
            dislocation_threshold=self.dislocation_threshold,
        )


def _leader(futures_pct_change: float, etf_pct_change: float) -> str:
    if abs(futures_pct_change) > abs(etf_pct_change):
        return "futures"
    return "etf"


def _divergence_band(
    divergence: float,
    *,
    clean_threshold: float,
    dislocation_threshold: float,
) -> str:
    if divergence < clean_threshold:
        return "low"
    if divergence <= dislocation_threshold:
        return "moderate"
    return "high"


def _explanation(direction_relation: str, leader: str, divergence_band: str) -> str:
    relation_label = direction_relation.replace("_", " ")
    return f"{relation_label.capitalize()}, {leader} leading, {divergence_band} divergence."
