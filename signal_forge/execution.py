from __future__ import annotations

from signal_forge.contracts import ConflictResult, ExecutionInput, Thesis


class ExecutionInterface:
    def build_input(self, thesis: Thesis, conflict: ConflictResult) -> ExecutionInput:
        return ExecutionInput(thesis=thesis, conflict=conflict)

    def decision_label(self, execution_input: ExecutionInput) -> str:
        if not execution_input.conflict.deployment_allowed:
            return "blocked"
        if execution_input.conflict.risk_level == "high":
            return "selective"
        return "deployable"
