from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from signal_forge.data import LiveDataUnavailableError, build_live_context, fetch_market_snapshot
from signal_forge.data.live_fetch import REQUIRED_TICKERS
from signal_forge.pipeline import SignalForgePipeline

LOG_DIR = Path("signal_forge/logs")
AUDIT_LOG_PATH = LOG_DIR / "live_pipeline_audit.jsonl"
DECISION_LOG_PATH = LOG_DIR / "decision_log.jsonl"


def run_live_pipeline(snapshot: dict[str, dict[str, object]] | None = None) -> dict[str, object]:
    try:
        live_snapshot = snapshot or fetch_market_snapshot()
    except LiveDataUnavailableError as exc:
        return {"status": "skipped", "reason": str(exc)}
    if not _snapshot_complete(live_snapshot):
        return {"status": "skipped", "reason": "missing required ticker"}

    pipeline = SignalForgePipeline(AUDIT_LOG_PATH)
    context = build_live_context(live_snapshot)
    with redirect_stdout(io.StringIO()):
        result = pipeline.run(context)
    entry = _append_decision_log(live_snapshot, result)
    ready_count = 1 if entry["execution_status"] == "ready" else 0
    blocked_count = 1 - ready_count
    return {
        "status": "ok",
        "decision": result["log_entry"]["decision"],
        "regime": entry["regime"],
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "log_path": str(DECISION_LOG_PATH),
    }


def _snapshot_complete(snapshot: dict[str, dict[str, object]]) -> bool:
    return all(
        isinstance(snapshot.get(ticker), dict) and snapshot[ticker].get("day_chg") is not None
        for ticker in REQUIRED_TICKERS
    )


def _append_decision_log(snapshot: dict[str, dict[str, object]], result: dict[str, object]) -> dict[str, object]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    meta = snapshot.get("_meta", {})
    payload = {
        "timestamp": meta.get("fetched_at"),
        "source": ",".join(meta.get("sources", [])) or "unavailable",
        "missing_tickers": meta.get("missing_tickers", []),
        "symbol": "SPY",
        "regime": result["agent_outputs"]["macro"]["state"],
        "market_quality": result["agent_outputs"]["market_quality"]["state"],
        "candidate_score": result["execution_input"]["confidence_score"],
        "policy_decision": "pass" if result["conflict"]["deployment_allowed"] else "block",
        "policy_reason": result["conflict"]["notes"],
        "execution_status": "ready" if result["safeguards"]["allowed"] else "blocked",
        "execution_reason": result["safeguards"]["reason"],
        "sized": False,
        "side": result["thesis"]["direction"],
    }
    with DECISION_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True))
        handle.write("\n")
    return payload


def main() -> None:
    result = run_live_pipeline()
    if result["status"] == "skipped":
        print("DATA FETCH FAILED — SKIPPING RUN")
        return
    print(f"REGIME: {result['regime']}")
    print(f"TRADES: READY={result['ready_count']} BLOCKED={result['blocked_count']}")


if __name__ == "__main__":
    main()
