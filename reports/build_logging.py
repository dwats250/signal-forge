from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPORT_TIMEZONE = ZoneInfo("America/Vancouver")
ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT_DIR / "logs" / "report_build.log"


def report_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(REPORT_TIMEZONE)
    if now.tzinfo is None:
        return now.replace(tzinfo=REPORT_TIMEZONE)
    return now.astimezone(REPORT_TIMEZONE)


def report_timestamp(now: datetime | None = None) -> str:
    return report_now(now).strftime("%Y-%m-%d %H:%M:%S PST")


def generated_line(now: datetime | None = None) -> str:
    return report_now(now).strftime("Generated at %-I:%M PST — %Y-%m-%d")


def append_report_log(stage: str, status: str, message: str = "", *, now: datetime | None = None) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    suffix = f" | {message}" if message else ""
    line = f"{report_timestamp(now)} | stage={stage} | status={status}{suffix}\n"
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line)


def append_data_source_log(symbol: str, source: str, *, fallback_used: bool = False, stale_risk: bool = False) -> None:
    message = f"{symbol} -> {source.upper()}"
    if fallback_used:
        message += " (fallback)"
    if stale_risk:
        message += " (stale risk)"
    append_report_log("data.health", "info", message)


def append_confidence_score_log(score: int) -> None:
    append_report_log("data.health", "info", f"CONFIDENCE SCORE -> {score}")


def write_json_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def append_jsonl_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True))
        handle.write("\n")
