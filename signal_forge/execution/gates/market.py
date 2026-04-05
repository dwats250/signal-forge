from __future__ import annotations


def evaluate_market_gate(regime: dict[str, object] | None) -> dict[str, object]:
    if regime is None:
        return {"passed": False, "reason": "missing market regime input"}

    approved = regime.get("approved")
    if approved is None:
        return {"passed": False, "reason": "missing market approval flag"}
    if not isinstance(approved, bool):
        return {"passed": False, "reason": "market approval flag must be boolean"}
    if not approved:
        return {"passed": False, "reason": str(regime.get("reason", "market gate failed"))}
    return {"passed": True, "reason": str(regime.get("reason", "market gate passed"))}
