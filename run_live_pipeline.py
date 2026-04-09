from __future__ import annotations

import argparse
import io
import json
import os
import traceback
from contextlib import redirect_stdout
from pathlib import Path

from signal_forge.data import build_live_context
from signal_forge.data.live_fetch import REQUIRED_TICKERS, SnapshotFetchResult, collect_market_snapshot
from signal_forge.execution.orchestrator import build_execution_health_payload
from signal_forge.pipeline import SignalForgePipeline

LOG_DIR = Path("signal_forge/logs")
AUDIT_LOG_PATH = LOG_DIR / "live_pipeline_audit.jsonl"
DECISION_LOG_PATH = LOG_DIR / "decision_log.jsonl"
DEBUG_ENV_VAR = "SIGNAL_FORGE_DEBUG_FETCH"
SNAPSHOT_SHAPE_ERROR = "DATA SHAPE FAILED — EXPECTED DICT SNAPSHOT"


def run_live_pipeline(
    snapshot: dict[str, dict[str, object]] | None = None,
    *,
    debug: bool = False,
) -> dict[str, object]:
    if snapshot is not None and not isinstance(snapshot, dict):
        return _shape_failure_result()

    try:
        fetch_result = _snapshot_fetch_result(snapshot)
    except Exception as exc:
        if debug or _debug_enabled():
            traceback.print_exc()
        return {
            "status": "skipped",
            "reason": str(exc),
            "pipeline_mode": "unavailable",
            "decision": "skip",
            "diagnostics": [
                {
                    "provider": "pipeline",
                    "group": "fetch",
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "fatal": True,
                }
            ],
        }

    live_snapshot = fetch_result.snapshot
    if not isinstance(live_snapshot, dict):
        return _shape_failure_result()
    if not _snapshot_complete(live_snapshot) and fetch_result.fatal:
        return _skipped_result(fetch_result, "minimum viable dataset unavailable")

    pipeline = SignalForgePipeline(AUDIT_LOG_PATH)
    context = build_live_context(live_snapshot)
    with redirect_stdout(io.StringIO()):
        result = pipeline.run(context)
    entry = _append_decision_log(live_snapshot, result, fetch_result)
    ready_count = 1 if entry["execution_status"] == "ready" else 0
    blocked_count = 1 - ready_count
    return {
        "status": "ok",
        "pipeline_mode": fetch_result.mode,
        "decision": fetch_result.decision,
        "trade_decision": result["log_entry"]["decision"],
        "regime": entry["regime"],
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "log_path": str(DECISION_LOG_PATH),
        "missing_groups": fetch_result.missing_groups,
        "partial_groups": fetch_result.partial_groups,
        "missing_tickers": fetch_result.missing_tickers,
        "diagnostics": _finalize_diagnostics(fetch_result, fatal=False),
    }


def _snapshot_complete(snapshot: dict[str, dict[str, object]]) -> bool:
    return all(
        isinstance(snapshot.get(ticker), dict) and snapshot[ticker].get("day_chg") is not None
        for ticker in REQUIRED_TICKERS
    )


def _append_decision_log(
    snapshot: dict[str, dict[str, object]],
    result: dict[str, object],
    fetch_result: SnapshotFetchResult,
) -> dict[str, object]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    meta = snapshot.get("_meta", {})
    payload = {
        "timestamp": meta.get("fetched_at"),
        "source": ",".join(meta.get("sources", [])) or "unavailable",
        "missing_tickers": meta.get("missing_tickers", []),
        "missing_groups": meta.get("missing_groups", []),
        "partial_groups": meta.get("partial_groups", []),
        "pipeline_mode": fetch_result.mode,
        "pipeline_decision": fetch_result.decision,
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
    health = build_execution_health_payload(
        market_context={
            "regime": payload["regime"],
            "market_quality": payload["market_quality"],
            "data_confidence_score": result["execution_input"]["confidence_score"],
            "core_macro_health": meta.get("core_macro_health", "healthy"),
            "fail_safe_no_trade": bool(meta.get("fail_safe_no_trade")),
        },
        execution_status=str(payload["execution_status"]),
        execution_reason=str(payload["execution_reason"]),
        policy_decision=str(payload["policy_decision"]),
    )
    payload.update(health)
    with DECISION_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True))
        handle.write("\n")
    return payload


def _snapshot_fetch_result(snapshot: dict[str, dict[str, object]] | None) -> SnapshotFetchResult:
    if snapshot is not None:
        meta = snapshot.get("_meta", {})
        missing_tickers = sorted(
            ticker
            for ticker in REQUIRED_TICKERS
            if not isinstance(snapshot.get(ticker), dict) or snapshot[ticker].get("day_chg") is None
        )
        missing_groups = list(meta.get("missing_groups", []))
        partial_groups = list(meta.get("partial_groups", []))
        critical_missing_groups = list(meta.get("critical_missing_groups", []))
        mode = str(meta.get("mode") or ("degraded" if missing_tickers else "full"))
        decision = str(meta.get("decision") or ("skip" if critical_missing_groups else "proceed"))
        if not missing_groups or (missing_tickers and not critical_missing_groups and not partial_groups):
            from signal_forge.data.live_fetch import _classify_group_health  # local import avoids broad re-export churn

            missing_groups, partial_groups, critical_missing_groups = _classify_group_health(snapshot)
            mode = "unavailable" if critical_missing_groups else "degraded" if missing_tickers else "full"
            decision = "skip" if critical_missing_groups else "proceed"
        snapshot["_meta"] = {
            **meta,
            "fetched_at": meta.get("fetched_at"),
            "sources": meta.get("sources", []),
            "missing_tickers": missing_tickers,
            "missing_groups": missing_groups,
            "partial_groups": partial_groups,
            "critical_missing_groups": critical_missing_groups,
            "mode": mode,
            "decision": decision,
            "diagnostics": list(meta.get("diagnostics", [])),
        }
        return SnapshotFetchResult(
            snapshot=snapshot,
            diagnostics=list(snapshot["_meta"]["diagnostics"]),
            missing_tickers=missing_tickers,
            missing_groups=missing_groups,
            partial_groups=partial_groups,
            critical_missing_groups=critical_missing_groups,
            sources=list(snapshot["_meta"]["sources"]),
            mode=mode,
            decision=decision,
            fatal=bool(critical_missing_groups),
        )
    return collect_market_snapshot()


def _shape_failure_result() -> dict[str, object]:
    return {
        "status": "skipped",
        "reason": SNAPSHOT_SHAPE_ERROR,
        "pipeline_mode": "unavailable",
        "decision": "skip",
        "missing_groups": [],
        "partial_groups": [],
        "missing_tickers": REQUIRED_TICKERS,
        "diagnostics": [
            {
                "provider": "pipeline",
                "group": "snapshot",
                "status": "failed",
                "error_type": "DataShapeError",
                "error": SNAPSHOT_SHAPE_ERROR,
                "fatal": True,
            }
        ],
    }


def _skipped_result(fetch_result: SnapshotFetchResult, reason: str) -> dict[str, object]:
    return {
        "status": "skipped",
        "reason": reason,
        "pipeline_mode": fetch_result.mode,
        "decision": fetch_result.decision,
        "missing_groups": fetch_result.missing_groups,
        "partial_groups": fetch_result.partial_groups,
        "missing_tickers": fetch_result.missing_tickers,
        "diagnostics": _finalize_diagnostics(fetch_result, fatal=True),
    }


def _finalize_diagnostics(fetch_result: SnapshotFetchResult, *, fatal: bool) -> list[dict[str, object]]:
    finalized: list[dict[str, object]] = []
    for item in fetch_result.diagnostics:
        entry = dict(item)
        entry["fatal"] = bool(fatal and item.get("group") in fetch_result.critical_missing_groups)
        finalized.append(entry)
    return finalized


def _debug_enabled() -> bool:
    return os.getenv(DEBUG_ENV_VAR, "").strip().lower() in {"1", "true", "yes", "on"}


def _print_diagnostics(result: dict[str, object]) -> None:
    for item in result.get("diagnostics", []):
        parts = [
            "[fetch]",
            f"provider={item.get('provider', 'unknown')}",
            f"group={item.get('group', item.get('symbol', 'unknown'))}",
            f"status={item.get('status', 'unknown')}",
        ]
        if item.get("count") is not None:
            parts.append(f"count={item['count']}")
        if item.get("error_type"):
            parts.append(f"exception={item['error_type']}")
        if item.get("error"):
            parts.append(f"error={item['error']}")
        parts.append(f"fatal={'yes' if item.get('fatal') else 'no'}")
        print(" ".join(parts))

    missing_groups = ",".join(result.get("missing_groups", [])) or "none"
    partial_groups = ",".join(result.get("partial_groups", [])) or "none"
    print(
        f"[pipeline] mode={result.get('pipeline_mode', 'unknown')} render={result.get('decision', 'unknown')} "
        f"missing_groups={missing_groups} partial_groups={partial_groups}"
    )


def run_preflight(*, debug: bool = False) -> dict[str, object]:
    try:
        fetch_result = collect_market_snapshot()
    except Exception as exc:
        if debug or _debug_enabled():
            traceback.print_exc()
        return {
            "status": "skipped",
            "reason": str(exc),
            "pipeline_mode": "unavailable",
            "decision": "skip",
            "missing_groups": [],
            "partial_groups": [],
            "missing_tickers": REQUIRED_TICKERS,
            "diagnostics": [
                {
                    "provider": "pipeline",
                    "group": "fetch",
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "fatal": True,
                }
            ],
        }
    result = {
        "status": "skipped" if fetch_result.fatal else "ok",
        "reason": "minimum viable dataset unavailable" if fetch_result.fatal else None,
        "pipeline_mode": fetch_result.mode,
        "decision": fetch_result.decision,
        "missing_groups": fetch_result.missing_groups,
        "partial_groups": fetch_result.partial_groups,
        "missing_tickers": fetch_result.missing_tickers,
        "diagnostics": _finalize_diagnostics(fetch_result, fatal=fetch_result.fatal),
    }
    return {
        "status": result["status"],
        "reason": result.get("reason"),
        "pipeline_mode": result.get("pipeline_mode"),
        "decision": result.get("decision"),
        "missing_groups": result.get("missing_groups", []),
        "partial_groups": result.get("partial_groups", []),
        "missing_tickers": result.get("missing_tickers", []),
        "diagnostics": result.get("diagnostics", []),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the live Signal Forge pipeline")
    parser.add_argument("--preflight", action="store_true", help="Check live fetch dependencies without running the pipeline")
    parser.add_argument("--debug", action="store_true", help="Print full traceback on unexpected failures")
    args = parser.parse_args(argv)

    result = run_preflight(debug=args.debug) if args.preflight else run_live_pipeline(debug=args.debug)
    _print_diagnostics(result)
    if result["status"] == "skipped":
        print(f"DATA FETCH FAILED — SKIPPING RUN ({result.get('reason', 'minimum dataset unavailable')})")
        return
    if args.preflight:
        print("PREFLIGHT OK")
        return
    print(f"REGIME: {result['regime']}")
    print(f"TRADES: READY={result['ready_count']} BLOCKED={result['blocked_count']}")


if __name__ == "__main__":
    main()
