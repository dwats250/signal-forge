from __future__ import annotations

from pathlib import Path
from typing import Any

from signal_forge.agents import GeoAgent, MacroAgent, MarketQualityAgent, OptionsBehaviorAgent
from signal_forge.audit import AuditLogger
from signal_forge.conflict_rules import ConflictRulesEngine
from signal_forge.execution import ExecutionInterface
from signal_forge.thesis_engine import ThesisEngine


class SignalForgePipeline:
    def __init__(self, log_path: Path) -> None:
        self.agents = {
            "macro": MacroAgent(),
            "geo": GeoAgent(),
            "market_quality": MarketQualityAgent(),
            "options": OptionsBehaviorAgent(),
        }
        self.thesis_engine = ThesisEngine()
        self.conflict_engine = ConflictRulesEngine()
        self.execution_interface = ExecutionInterface()
        self.audit_logger = AuditLogger(log_path)

    def run(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        outputs = {
            domain: agent.run(context)
            for domain, agent in self.agents.items()
        }
        thesis = self.thesis_engine.build(outputs)
        conflict = self.conflict_engine.evaluate(thesis)
        execution_input = self.execution_interface.build_input(thesis, conflict)
        decision = self.execution_interface.decision_label(execution_input)
        log_entry = self.audit_logger.write(execution_input, decision, conflict.notes)
        return {
            "agent_outputs": {domain: output.to_dict() for domain, output in outputs.items()},
            "thesis": thesis.to_dict(),
            "conflict": conflict.to_dict(),
            "execution_input": execution_input.to_dict(),
            "log_entry": log_entry.to_dict(),
        }
