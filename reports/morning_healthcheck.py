from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from reports.build_logging import append_jsonl_file, report_now, write_json_file
from signal_forge.execution.orchestrator import (
    build_execution_health_payload,
    normalize_execution_reason,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT_DIR / "logs"
HEALTHCHECK_LATEST_PATH = LOG_DIR / "morning_healthcheck.latest.json"
HEALTHCHECK_HISTORY_PATH = LOG_DIR / "morning_healthcheck.history.jsonl"
STATUS_PATH = LOG_DIR / "morning_status.txt"
DECISION_LOG_PATH = ROOT_DIR / "signal_forge" / "logs" / "decision_log.jsonl"


def _coerce_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def aggregate_setup_outcomes(entries: list[dict[str, Any]]) -> dict[str, Any]:
    block_reasons: Counter[str] = Counter()
    summary = {
        "ready": 0,
        "watchlist": 0,
        "blocked": 0,
        "block_reasons": {},
    }
    for entry in entries:
        outcome = str(entry.get("setup_outcome", "BLOCKED")).upper()
        if outcome == "READY":
            summary["ready"] += 1
            continue
        if outcome == "WATCHLIST":
            summary["watchlist"] += 1
        else:
            summary["blocked"] += 1
        normalized = normalize_execution_reason(
            entry.get("dominant_reason") or entry.get("execution_reason"),
            entry,
            policy_decision=entry.get("policy_decision"),
            execution_status=entry.get("execution_status"),
        ) or "UNKNOWN"
        block_reasons[normalized] += 1
    summary["block_reasons"] = dict(sorted(block_reasons.items()))
    return summary


def summarize_execution_log(entries: list[dict[str, Any]]) -> dict[str, Any]:
    setup_counts = aggregate_setup_outcomes(entries)
    latest = entries[-1] if entries else {}
    top_block_reason = "NONE"
    ranked_reasons = {
        key: value
        for key, value in setup_counts["block_reasons"].items()
        if key != "UNKNOWN"
    }
    if ranked_reasons:
        top_block_reason = max(
            ranked_reasons.items(),
            key=lambda item: (item[1], item[0]),
        )[0]
    elif setup_counts["block_reasons"]:
        top_block_reason = "UNKNOWN"
    return {
        "execution_mode": str(latest.get("execution_mode", "NO_TRADE")).upper(),
        "dominant_reason": latest.get("dominant_reason") or top_block_reason,
        "setup_counts": setup_counts,
        "top_block_reason": top_block_reason,
    }


def build_morning_healthcheck_summary(
    *,
    stage_statuses: dict[str, str],
    report_data: dict[str, Any],
    decision_log_path: Path = DECISION_LOG_PATH,
) -> dict[str, Any]:
    statuses = [status.lower() for status in stage_statuses.values()]
    success_count = sum(status == "success" for status in statuses)
    if success_count == len(statuses):
        build_status = "SUCCESS"
    elif success_count == 0:
        build_status = "FAILURE"
    else:
        build_status = "PARTIAL"

    market_data = report_data.get("market_data", {}) if isinstance(report_data, dict) else {}
    meta = market_data.get("_meta", {}) if isinstance(market_data, dict) else {}
    confidence_score = _coerce_int(
        report_data.get("confidence_score", meta.get("confidence_score")),
        default=0,
    )
    fallback_symbols = [str(item) for item in meta.get("fallback_symbols", []) if isinstance(item, str)]
    core_macro_status = str(meta.get("core_macro_health", "blind")).lower()

    decision_entries = _read_jsonl(decision_log_path)
    execution_summary = summarize_execution_log(decision_entries)
    if not decision_entries:
        execution_health = build_execution_health_payload(
            market_context={
                "data_confidence_score": confidence_score,
                "core_macro_health": core_macro_status,
            },
            execution_status="blocked",
            execution_reason="NO VALID CANDIDATES",
            policy_decision="pass",
        )
        execution_summary["execution_mode"] = execution_health["execution_mode"]
        execution_summary["dominant_reason"] = execution_health["dominant_reason"]
        execution_summary["top_block_reason"] = execution_health["dominant_reason"] or "NONE"

    summary = {
        "build_status": build_status,
        "timestamp": report_now().isoformat(),
        "stages": stage_statuses,
        "data_confidence_score": confidence_score,
        "fallback_used": bool(fallback_symbols),
        "fallback_symbols": fallback_symbols,
        "core_macro_status": core_macro_status,
        "execution_mode": execution_summary["execution_mode"],
        "setup_counts": {
            "ready": execution_summary["setup_counts"]["ready"],
            "watchlist": execution_summary["setup_counts"]["watchlist"],
            "blocked": execution_summary["setup_counts"]["blocked"],
        },
        "block_reasons": execution_summary["setup_counts"]["block_reasons"],
        "top_block_reason": execution_summary["top_block_reason"],
    }
    summary["notification_message"] = build_notification_message(summary)
    return summary


def write_healthcheck_outputs(summary: dict[str, Any]) -> None:
    write_json_file(HEALTHCHECK_LATEST_PATH, summary)
    append_jsonl_file(HEALTHCHECK_HISTORY_PATH, summary)
    STATUS_PATH.write_text(build_status_file(summary), encoding="utf-8")


def build_cli_summary(summary: dict[str, Any]) -> str:
    fallback = ", ".join(summary.get("fallback_symbols", [])) or "none"
    counts = summary.get("setup_counts", {})
    lines = [
        "=== MORNING HEALTHCHECK ===",
        f"BUILD: {summary.get('build_status', 'FAILURE')}",
        f"DATA CONFIDENCE: {summary.get('data_confidence_score', 0)}",
        f"CORE MACRO: {str(summary.get('core_macro_status', 'blind')).upper()}",
        f"FALLBACK USED: {fallback}",
        f"EXECUTION MODE: {summary.get('execution_mode', 'NO_TRADE')}",
        (
            "SETUPS: "
            f"READY {counts.get('ready', 0)} | "
            f"WATCHLIST {counts.get('watchlist', 0)} | "
            f"BLOCKED {counts.get('blocked', 0)}"
        ),
        f"TOP BLOCK: {summary.get('top_block_reason', 'NONE')}",
        "===========================",
    ]
    return "\n".join(lines)


def build_status_file(summary: dict[str, Any]) -> str:
    counts = summary.get("setup_counts", {})
    return "\n".join(
        [
            f"BUILD={summary.get('build_status', 'FAILURE')}",
            f"CONFIDENCE={summary.get('data_confidence_score', 0)}",
            f"CORE_MACRO={str(summary.get('core_macro_status', 'blind')).upper()}",
            f"EXECUTION={summary.get('execution_mode', 'NO_TRADE')}",
            f"READY={counts.get('ready', 0)}",
            f"WATCHLIST={counts.get('watchlist', 0)}",
            f"BLOCKED={counts.get('blocked', 0)}",
            f"TOP_BLOCK={summary.get('top_block_reason', 'NONE')}",
        ]
    )


def build_notification_message(summary: dict[str, Any]) -> str:
    counts = summary.get("setup_counts", {})
    fallback_symbols = ",".join(summary.get("fallback_symbols", []))
    parts = [
        f"Morning Edge {summary.get('build_status', 'FAILURE')}",
        f"Confidence {summary.get('data_confidence_score', 0)}",
        str(summary.get("execution_mode", "NO_TRADE")),
        f"Ready {counts.get('ready', 0)} Watchlist {counts.get('watchlist', 0)}",
    ]
    if fallback_symbols:
        parts.append(f"Fallback: {fallback_symbols}")
    return " | ".join(parts)
