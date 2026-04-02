from __future__ import annotations

import json
from pathlib import Path

from signal_forge.contracts import ExecutionInput, LogEntry


class AuditLogger:
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, execution_input: ExecutionInput, decision: str, notes: str) -> LogEntry:
        entry = LogEntry.create(
            thesis_id=execution_input.thesis.thesis_id,
            decision=decision,
            notes=notes,
        )
        payload = {
            "log_entry": entry.to_dict(),
            "execution_input": execution_input.to_dict(),
        }
        with self.output_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True))
            handle.write("\n")
        return entry
