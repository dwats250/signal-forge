from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from signal_forge.agents import (
    DislocationFetcher,
    GeoAgent,
    MacroAgent,
    MarketQualityAgent,
    OptionsBehaviorAgent,
)
from signal_forge.contracts import DislocationReading
from signal_forge.audit import AuditLogger
from signal_forge.config import USE_OPENWOLF
from signal_forge.conflict_rules import ConflictRulesEngine
from signal_forge.dislocation_engine import classify_dislocation
from signal_forge.execution import ExecutionInterface
from signal_forge.memory.openwolf_adapter import store_context
from signal_forge.memory.retrieval import find_similar_context
from signal_forge.memory.schema import build_memory_record
from signal_forge.thesis_engine import ThesisEngine


class SignalForgePipeline:
    def __init__(self, log_path: Path) -> None:
        self.agents = {
            "macro": MacroAgent(),
            "geo": GeoAgent(),
            "market_quality": MarketQualityAgent(),
            "options": OptionsBehaviorAgent(),
        }
        self.dislocation_fetcher = DislocationFetcher()
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
        fetched = self.dislocation_fetcher.fetch("CL", "XLE", context)
        reading = DislocationReading(
            futures_symbol="CL",
            etf_symbol="XLE",
            futures_pct_change=fetched["futures_pct_change"],
            etf_pct_change=fetched["etf_pct_change"],
        )
        dislocation = classify_dislocation(reading)
        print(
            f"[{dislocation.signal}] {dislocation.pair} | divergence: "
            f"{dislocation.divergence:.2f}% | relation: {dislocation.direction_relation} "
            f"| leader: {dislocation.leader}"
        )
        print(f"Explanation: {dislocation.explanation}")

        memory_annotation: str | None = None
        if USE_OPENWOLF:
            try:
                record = build_memory_record(reading, dislocation)
                prefix = f"{record['symbol']} {record['signal']}"
                store_context(f"{prefix} | {json.dumps(record)}")
                similar = find_similar_context(dislocation.pair, dislocation.signal)
                count = len([l for l in similar.splitlines() if l.strip()])
                if count > 0:
                    memory_annotation = f"Memory: {count} similar cases found"
            except Exception:
                pass

        thesis = self.thesis_engine.build(outputs)
        conflict = self.conflict_engine.evaluate(thesis)
        execution_input = self.execution_interface.build_input(thesis, conflict)
        decision = self.execution_interface.decision_label(execution_input)
        log_entry = self.audit_logger.write(execution_input, decision, conflict.notes)
        result: dict[str, Any] = {
            "agent_outputs": {domain: output.to_dict() for domain, output in outputs.items()},
            "dislocation_signal": dislocation.to_dict(),
            "thesis": thesis.to_dict(),
            "conflict": conflict.to_dict(),
            "execution_input": execution_input.to_dict(),
            "log_entry": log_entry.to_dict(),
        }
        if memory_annotation is not None:
            result["memory"] = memory_annotation
        return result
