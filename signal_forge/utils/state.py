from __future__ import annotations


def build_state_block(root_cause, evidence, next_target) -> str:
    payload = root_cause if isinstance(root_cause, dict) else {}
    task = str(payload.get("task", root_cause)).strip()
    status = str(payload.get("status", "PASS")).strip().upper()
    if status not in {"PASS", "FAIL", "BLOCKED"}:
        status = "BLOCKED"
    working = payload.get("working", evidence)
    working = [str(item).strip() for item in (working if isinstance(working, list) else [working]) if str(item).strip()]
    issues = payload.get("issues", [])
    issues = [str(item).strip() for item in (issues if isinstance(issues, list) else [issues]) if str(item).strip()] or ["none"]
    next_items = payload.get("next", next_target)
    next_items = [str(item).strip() for item in (next_items if isinstance(next_items, list) else [next_items]) if str(item).strip()]
    next_value = next_items[0] if next_items else "none"
    lines = ["## STATE", "", "Task", f"- {task}", "", "Status", f"- {status}", "", "Working"]
    lines.extend(f"- {item}" for item in working)
    lines.extend(["", "Issues"])
    lines.extend(f"- {item}" for item in issues)
    lines.extend(["", "Next", f"- {next_value}"])
    return "\n".join(lines)
