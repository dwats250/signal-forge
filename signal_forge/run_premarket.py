"""
Premarket pipeline entry point — Layer 1 → Layer 10.

Run via:  python -m signal_forge.run_premarket

Exits 0 on success, 1 on pipeline halt or unhandled error.
Writes .sf_commit_msg for the CI commit step to consume.
"""

from __future__ import annotations

import logging
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("signal_forge.run_premarket")

_COMMIT_MSG_PATH = Path(".sf_commit_msg")


def _write_commit_msg(msg: str) -> None:
    _COMMIT_MSG_PATH.write_text(msg, encoding="utf-8")


def main() -> int:
    run_dt    = datetime.now(tz=timezone.utc)
    date_str  = run_dt.strftime("%Y-%m-%d")
    t_start   = time.monotonic()

    import signal_forge.audit as audit_mod
    run_id = audit_mod.new_run_id()
    logger.info("Run %s  %s  pid=%d", run_id[:8], date_str, __import__("os").getpid())

    # ── Layers 1–3: ingest, normalize, validate ──────────────────────────
    from signal_forge.ingestion import fetch_all
    from signal_forge.normalization import normalize_all
    from signal_forge.validation import PipelineHaltError, validate_all

    try:
        raw     = fetch_all()
        normed  = normalize_all(raw)
        results = validate_all(normed)
    except PipelineHaltError as halt:
        logger.error("PIPELINE HALT: %s", halt)
        halt_msg = (
            f"SF HALT: {date_str} | DATA INVALID | {halt.symbol} — {halt.reason}"
        )
        print(str(halt))
        _write_commit_msg(halt_msg)
        return 1

    # ── Layer 5: regime ──────────────────────────────────────────────────
    from signal_forge.regime import classify_regime, from_validation_results
    quotes = from_validation_results(results)
    regime = classify_regime(quotes)

    # ── Layer 4: derived metrics ─────────────────────────────────────────
    from signal_forge.derived import compute_all
    vix_level = quotes["^VIX"].price if "^VIX" in quotes else 20.0
    metrics   = compute_all(quotes, vix_level=vix_level)

    # ── Layer 6: structure ───────────────────────────────────────────────
    from signal_forge.structure import classify_all
    spy_pct  = quotes["SPY"].pct_change_decimal if "SPY" in quotes else None
    readings = classify_all(quotes, metrics, spy_pct_change=spy_pct, vix_level=vix_level)
    chop_log = [sym for sym, r in readings.items() if r.disqualified]

    # ── Layer 7: qualification ───────────────────────────────────────────
    from signal_forge.qualification import qualify_all
    qual = qualify_all(quotes, readings, metrics, regime)

    # ── Layer 8: options expression ──────────────────────────────────────
    from signal_forge.options import express_all
    expressions = express_all(qual)

    # ── Layer 9: output ──────────────────────────────────────────────────
    from signal_forge.output import (
        render_markdown,
        render_terminal,
        send_pushover,
        write_markdown,
    )

    chop_tradeable = [
        s for s in chop_log
        if not s.startswith("^") and s not in {"DX-Y.NYB", "BTC-USD"}
    ]

    terminal   = render_terminal(regime, expressions, qual, results, quotes, chop_log, run_dt)
    md_content = render_markdown(regime, expressions, qual, results, quotes, chop_log, run_dt)
    md_path    = write_markdown(md_content, run_dt)
    pushed, push_err = send_pushover(regime, expressions, qual, len(chop_tradeable), run_dt)

    print(terminal)

    # ── Layer 10: audit ──────────────────────────────────────────────────
    counts  = Counter(r.status for r in qual)
    elapsed = time.monotonic() - t_start
    record  = audit_mod.build_record(
        run_id=run_id,
        started_at=run_dt,
        regime_state=regime,
        trade_count=len(expressions),
        watchlist_count=counts["WATCHLIST"],
        rejected_count=counts["REJECTED"],
        chop_count=len(chop_tradeable),
        symbols_valid=sum(1 for r in results if r.passed),
        symbols_invalid=sum(1 for r in results if not r.passed),
        output_paths=[str(md_path)],
        pushover_sent=pushed,
        pushover_error=push_err,
        elapsed_seconds=elapsed,
    )
    audit_mod.write(record)

    # ── Commit message ───────────────────────────────────────────────────
    tickers = [e.symbol for e in expressions]
    ticker_str = ", ".join(tickers) if tickers else ""
    commit_msg = (
        f"SF report: {date_str} | {regime.regime} | "
        f"{len(expressions)} trades [{ticker_str}]"
    )
    _write_commit_msg(commit_msg)
    logger.info("Done in %.1fs — %s", elapsed, commit_msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
