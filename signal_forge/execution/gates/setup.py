from __future__ import annotations

from signal_forge.execution.models import TradeCandidate


def evaluate_setup_gate(
    candidate: TradeCandidate,
    setup: dict[str, object] | None,
) -> dict[str, object]:
    if setup is None:
        return {"valid": False, "reason": "missing setup gate input"}

    valid = setup.get("valid")
    if valid is None:
        return {"valid": False, "reason": "missing setup validity flag"}
    if not isinstance(valid, bool):
        return {"valid": False, "reason": "setup validity flag must be boolean"}
    if not valid:
        return {"valid": False, "reason": str(setup.get("reason", "setup gate failed"))}

    conflict_direction = setup.get("direction")
    if conflict_direction is not None and conflict_direction != candidate.direction.value:
        return {"valid": False, "reason": "setup direction conflicts with trade direction"}
    return {"valid": True, "reason": str(setup.get("reason", "setup gate passed"))}
