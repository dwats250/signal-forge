from __future__ import annotations

from typing import Any

from strategy_intel import storage
from strategy_intel.models import EdgeComponent


def _normalize_text(value: str) -> str:
    return value.strip().lower()


def _component_matches(component: EdgeComponent, tags: list[str]) -> bool:
    fields = (
        _normalize_text(component.name),
        _normalize_text(component.category),
        _normalize_text(component.notes),
    )
    for tag in tags:
        normalized_tag = _normalize_text(tag)
        if not normalized_tag:
            continue
        if any(normalized_tag in field for field in fields):
            return True
    return False


def _component_score(component: EdgeComponent) -> float:
    if component.score is None:
        return 0.0
    return float(component.score.total_score)


def gate_trade(trade: dict[str, Any]) -> dict[str, Any]:
    description = trade.get("description")
    tags = trade.get("tags")

    if not isinstance(description, str):
        raise ValueError("trade.description must be a string")
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise ValueError("trade.tags must be a list[str]")

    components = storage.load_components()
    matches = [component for component in components if _component_matches(component, tags)]

    if not matches:
        return {
            "decision": "FAIL",
            "matched_component": None,
            "score": 0.0,
            "reason": "No edge component matched trade tags.",
        }

    best_match = max(matches, key=_component_score)
    score = _component_score(best_match)

    if score < 3.5:
        return {
            "decision": "FAIL",
            "matched_component": best_match.name,
            "score": score,
            "reason": "Matched edge component score is below gate threshold.",
        }

    return {
        "decision": "PASS",
        "matched_component": best_match.name,
        "score": score,
        "reason": "Matched edge component score meets gate threshold.",
    }
