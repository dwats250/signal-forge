from __future__ import annotations

import json
from pathlib import Path

from signal_forge.execution.models import ExecutionPolicy, PolicyChange
from signal_forge.execution.models.core import utc_now


class PolicyStore:
    def __init__(self, log_path: Path, policy: ExecutionPolicy | None = None) -> None:
        self.log_path = log_path
        self.policy = policy or ExecutionPolicy()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def has_active_change(self) -> bool:
        return any(self._iter_changes())

    def apply_change(self, *, field: str, new_value: object, reason: str, review_window: int) -> PolicyChange:
        if not hasattr(self.policy, field):
            raise ValueError(f"unknown policy field: {field}")
        if self.has_active_change():
            raise ValueError("only one active policy change is allowed")

        previous_value = getattr(self.policy, field)
        setattr(self.policy, field, new_value)
        change = PolicyChange(
            timestamp=utc_now(),
            field=field,
            previous_value=previous_value,
            new_value=new_value,
            reason=reason,
            review_window=review_window,
        )
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(change.to_dict(), sort_keys=True))
            handle.write("\n")
        return change

    def _iter_changes(self) -> list[dict[str, object]]:
        if not self.log_path.exists():
            return []
        changes: list[dict[str, object]] = []
        with self.log_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    changes.append(json.loads(line))
        return changes
