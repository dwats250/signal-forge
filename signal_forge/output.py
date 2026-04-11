"""
Layer 9 — Output Engine

Writes three destinations per run:
  1. Terminal  — formatted to stdout
  2. Markdown  — reports/YYYY-MM-DD.md (append-safe; overwrites same-day file)
  3. Pushover  — push alert via api.pushover.net

NO TRADE and STAY_FLAT days still produce a full report at all three destinations.
Pushover requires PUSHOVER_USER_KEY and PUSHOVER_API_KEY in environment.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from signal_forge.options import OptionsExpression
from signal_forge.qualification import QualificationResult
from signal_forge.regime import RegimeState
from signal_forge.validation import ValidationResult

logger = logging.getLogger(__name__)

_REPORTS_DIR = Path("reports")
_LINE_WIDTH   = 72


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _bar(char: str = "═") -> str:
    return char * _LINE_WIDTH


def _rule(char: str = "─") -> str:
    return "  " + char * (_LINE_WIDTH - 2)


def _pct(v: float) -> str:
    return f"{v:+.2%}"


def _fmt_macro(regime: RegimeState, quotes: dict) -> str:
    """One-line macro snapshot."""
    vix  = f"VIX: {regime.vix_level:.2f} ({_pct(regime.vix_change)})"

    def _q(sym: str, label: str) -> str:
        q = quotes.get(sym)
        if q is None:
            return f"{label}: N/A"
        return f"{label}: {q.price:.2f} ({_pct(q.pct_change_decimal)})"

    dxy = _q("DX-Y.NYB", "DXY")
    tnx = _q("^TNX",     "TNX")
    btc_q = quotes.get("BTC-USD")
    btc = f"BTC: {_pct(btc_q.pct_change_decimal)}" if btc_q else "BTC: N/A"
    return f"  {vix}  {dxy}  {tnx}  {btc}"


def _fmt_data_status(
    val_results: list[ValidationResult],
    quotes: dict,
) -> str:
    """Compact data status line for required symbols."""
    required = ["^VIX", "DX-Y.NYB", "^TNX", "BTC-USD", "SPY", "QQQ", "IWM"]
    label_map = {"^VIX": "VIX", "DX-Y.NYB": "DXY", "^TNX": "TNX",
                 "BTC-USD": "BTC", "SPY": "SPY", "QQQ": "QQQ", "IWM": "IWM"}
    status_map = {r.symbol: r.passed for r in val_results}
    parts = [
        f"{label_map.get(s, s)} {'✓' if status_map.get(s, False) else '✗'}"
        for s in required
    ]
    return "  " + "  ".join(parts)


def _strategy_display(e: OptionsExpression) -> str:
    names = {
        "long_call_spread": "Long Call Spread",
        "bull_put_spread":  "Bull Put Spread",
        "long_put_spread":  "Long Put Spread",
        "bear_call_spread": "Bear Call Spread",
    }
    return names.get(e.strategy, e.strategy.replace("_", " ").title())


# ---------------------------------------------------------------------------
# 1. Terminal report
# ---------------------------------------------------------------------------

def render_terminal(
    regime: RegimeState,
    expressions: list[OptionsExpression],
    qual_results: list[QualificationResult],
    val_results: list[ValidationResult],
    quotes: dict,
    chop_log: list[str],
    run_dt: datetime,
) -> str:
    """Build the full terminal report as a string."""
    date_str = run_dt.strftime("%Y-%m-%d (%a)")
    ts_str   = run_dt.strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []

    # ── Header ──────────────────────────────────────────────────────────
    lines.append(_bar("═"))
    lines.append(f"  SIGNAL FORGE {'─' * 20} {date_str}")
    lines.append(
        f"  Regime: {regime.regime:<12}  Posture: {regime.posture:<18}  "
        f"Confidence: {regime.confidence:.0%}"
    )
    lines.append(_fmt_macro(regime, quotes))
    lines.append(_bar("═"))

    # ── Trades ──────────────────────────────────────────────────────────
    trades = [q for q in qual_results if q.status == "TRADE"]

    if expressions:
        lines.append(f"\n  ■ VALIDATED TRADES ({len(expressions)})\n")
        for e in expressions:
            strat = _strategy_display(e)
            dir_lbl = e.direction.upper()
            lines.append(f"    {e.symbol:<8}  {dir_lbl:<5}  {strat}")
            lines.append(
                f"    Entry {e.entry:.2f}  Stop {e.stop:.2f}  "
                f"Target {e.target:.2f}  R:R {e.stop:.0f}:{e.target:.0f}"
            )
            strike_lbl = (
                f"sell ${e.short_strike:.0f} / buy ${e.long_strike:.0f}"
                if e.strategy in ("bull_put_spread", "bear_call_spread")
                else f"buy ${e.long_strike:.0f} / sell ${e.short_strike:.0f}"
            )
            lines.append(
                f"    Strikes: {strike_lbl}  |  DTE: {e.dte_min}–{e.dte_max}"
            )
            size_note = " (size ×0.5 — HIGH_IV)" if e.size_reduced else ""
            lines.append(
                f"    Size: {e.max_contracts} contract(s)  "
                f"Max risk: ${e.max_risk_dollars:.0f}{size_note}"
            )
            lines.append(
                f"    Exit: {e.exit_profit_target}  |  Loss: {e.exit_loss}"
            )
            lines.append(
                f"    IV: {e.iv_environment}  |  Structure: {e.structure}"
            )
            lines.append("")
    else:
        lines.append("\n  ■ NO TRADE")
        lines.append(f"    {regime.regime} / {regime.posture} — "
                     f"{'regime not tradeable' if not regime.tradeable else 'no qualified setups'}")
        lines.append("")

    # ── Watchlist ────────────────────────────────────────────────────────
    watchlist = [q for q in qual_results if q.status == "WATCHLIST"]
    lines.append(_rule())
    lines.append(f"  Watchlist ({len(watchlist)})")
    if watchlist:
        for q in watchlist:
            s = q.setup
            lines.append(
                f"    ~ {s.symbol:<8}  {s.direction.upper():<5}  "
                f"entry={s.entry:.2f}  |  {q.watchlist_condition}"
            )
    else:
        lines.append("    — none —")

    # ── Excluded ─────────────────────────────────────────────────────────
    _NON_TRADEABLE = {"^VIX", "DX-Y.NYB", "^TNX", "BTC-USD"}
    tradeable_chop = [s for s in chop_log if s not in _NON_TRADEABLE and not s.startswith("^")]
    rejected = [q for q in qual_results if q.status == "REJECTED"]

    lines.append(_rule())
    lines.append("  Excluded")
    if tradeable_chop:
        lines.append(f"    CHOP  ({len(tradeable_chop)}):  {' '.join(sorted(tradeable_chop))}")

    # Show non-CHOP rejected (direction mismatch, earnings, etc.) briefly
    non_chop_rejected = [
        q for q in rejected
        if q.rejection_reason and "STAY_FLAT" not in q.rejection_reason
        and "CHAOTIC" not in q.rejection_reason
    ]
    if non_chop_rejected:
        lines.append(f"    Rejected ({len(non_chop_rejected)}):")
        for q in non_chop_rejected[:8]:  # cap display at 8
            short = (q.rejection_reason or "")[:60]
            lines.append(f"      {q.symbol:<8}  {short}")

    # ── Data Status ──────────────────────────────────────────────────────
    lines.append(_rule())
    lines.append("  Data Status")
    lines.append(_fmt_data_status(val_results, quotes))
    valid_n   = sum(1 for r in val_results if r.passed)
    invalid_n = sum(1 for r in val_results if not r.passed)
    lines.append(
        f"  Symbols: {valid_n} valid / {invalid_n} invalid  |  "
        f"Source: yfinance  |  Run: {ts_str}"
    )

    lines.append(_bar("═"))
    return "\n".join(lines)


def print_report(report: str) -> None:
    print(report)


# ---------------------------------------------------------------------------
# 2. Markdown report
# ---------------------------------------------------------------------------

def render_markdown(
    regime: RegimeState,
    expressions: list[OptionsExpression],
    qual_results: list[QualificationResult],
    val_results: list[ValidationResult],
    quotes: dict,
    chop_log: list[str],
    run_dt: datetime,
) -> str:
    """Build the markdown report as a string."""
    date_str = run_dt.strftime("%Y-%m-%d")
    ts_str   = run_dt.strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []

    lines.append(f"# Signal Forge — {date_str}")
    lines.append("")
    lines.append(
        f"**Regime:** {regime.regime} | "
        f"**Posture:** {regime.posture} | "
        f"**Confidence:** {regime.confidence:.0%}"
    )
    q = quotes
    def _mq(sym, lbl):
        qq = q.get(sym)
        return f"**{lbl}:** {qq.price:.2f} ({_pct(qq.pct_change_decimal)})" if qq else f"**{lbl}:** N/A"
    lines.append(
        f"{_mq('^VIX','VIX')} | {_mq('DX-Y.NYB','DXY')} | "
        f"{_mq('^TNX','TNX')} | {_mq('BTC-USD','BTC')}"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Trades
    if expressions:
        lines.append(f"## Validated Trades ({len(expressions)})")
        lines.append("")
        for e in expressions:
            strat = _strategy_display(e)
            lines.append(f"### {e.symbol} — {e.direction.upper()} — {strat}")
            lines.append("")
            lines.append(f"| Field | Value |")
            lines.append(f"|---|---|")
            lines.append(f"| Entry | {e.entry:.2f} |")
            lines.append(f"| Stop | {e.stop:.2f} |")
            lines.append(f"| Target | {e.target:.2f} |")
            long_s = f"${e.long_strike:.0f}"
            short_s = f"${e.short_strike:.0f}"
            lines.append(f"| Long strike | {long_s} |")
            lines.append(f"| Short strike | {short_s} |")
            lines.append(f"| Spread width | ${e.spread_width:.2f} |")
            lines.append(f"| DTE range | {e.dte_min}–{e.dte_max} |")
            lines.append(f"| Max contracts | {e.max_contracts} |")
            lines.append(f"| Max risk | ${e.max_risk_dollars:.0f} |")
            lines.append(f"| Exit (profit) | {e.exit_profit_target} |")
            lines.append(f"| Exit (loss) | {e.exit_loss} |")
            lines.append(f"| IV env | {e.iv_environment} |")
            if e.size_reduced:
                lines.append(f"| Note | Size reduced 50% — HIGH\\_IV |")
            lines.append("")
    else:
        lines.append("## NO TRADE")
        lines.append("")
        lines.append(
            f"{regime.regime} / {regime.posture} — "
            f"{'regime not tradeable' if not regime.tradeable else 'no qualified setups'}"
        )
        lines.append("")

    # Watchlist
    watchlist = [q for q in qual_results if q.status == "WATCHLIST"]
    lines.append("## Watchlist")
    lines.append("")
    if watchlist:
        for q in watchlist:
            s = q.setup
            lines.append(f"- **{s.symbol}** {s.direction.upper()} @ {s.entry:.2f} — _{q.watchlist_condition}_")
    else:
        lines.append("*None*")
    lines.append("")

    # Excluded
    _NON_TRADEABLE = {"^VIX", "DX-Y.NYB", "^TNX", "BTC-USD"}
    tradeable_chop = [s for s in chop_log if s not in _NON_TRADEABLE and not s.startswith("^")]
    lines.append("## Excluded")
    lines.append("")
    if tradeable_chop:
        lines.append(f"**CHOP ({len(tradeable_chop)}):** {', '.join(sorted(tradeable_chop))}")
        lines.append("")

    non_chop_rejected = [
        q for q in qual_results
        if q.status == "REJECTED"
        and q.rejection_reason
        and "STAY_FLAT" not in q.rejection_reason
        and "CHAOTIC" not in q.rejection_reason
    ]
    if non_chop_rejected:
        lines.append(f"**Rejected ({len(non_chop_rejected)}):**")
        lines.append("")
        for q in non_chop_rejected:
            lines.append(f"- {q.symbol}: {q.rejection_reason}")
        lines.append("")

    # Data status
    lines.append("## Data Status")
    lines.append("")
    lines.append("| Symbol | Status | Source |")
    lines.append("|---|---|---|")
    status_map = {r.symbol: r for r in val_results}
    for sym, r in status_map.items():
        tick = "✓" if r.passed else "✗"
        src  = r.quote.source if r.quote else "—"
        lines.append(f"| {sym} | {tick} | {src} |")
    lines.append("")
    lines.append(f"*Run: {ts_str} | Signal Forge V2*")
    lines.append("")

    return "\n".join(lines)


def write_markdown(content: str, run_dt: datetime, directory: Path = _REPORTS_DIR) -> Path:
    """Write markdown to reports/YYYY-MM-DD.md. Returns the path written."""
    directory.mkdir(parents=True, exist_ok=True)
    filename = run_dt.strftime("%Y-%m-%d") + ".md"
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    logger.info("Markdown written: %s", path)
    return path


# ---------------------------------------------------------------------------
# 3. Pushover alert
# ---------------------------------------------------------------------------

_PUSHOVER_URL = "https://api.pushover.net/1/messages.json"


def _pushover_message(
    regime: RegimeState,
    expressions: list[OptionsExpression],
    qual_results: list[QualificationResult],
    chop_count: int,
    run_dt: datetime,
) -> tuple[str, str]:
    """Return (title, message) for Pushover."""
    date_str     = run_dt.strftime("%Y-%m-%d")
    watchlist    = [q for q in qual_results if q.status == "WATCHLIST"]
    trade_count  = len(expressions)

    if trade_count > 0:
        title = f"SF {date_str} | {trade_count} TRADE{'S' if trade_count > 1 else ''}"
        trade_lines = "\n".join(
            f"  {e.symbol} {e.direction.upper()} {_strategy_display(e)}"
            for e in expressions
        )
        msg = (
            f"{regime.regime}/{regime.posture} ({regime.confidence:.0%})\n"
            f"VIX {regime.vix_level:.2f}\n\n"
            f"TRADES:\n{trade_lines}"
        )
    else:
        title = f"SF {date_str} | NO TRADE"
        msg = (
            f"{regime.regime}/{regime.posture} ({regime.confidence:.0%})\n"
            f"VIX {regime.vix_level:.2f} | "
            f"{chop_count} CHOP | "
            f"{len(watchlist)} watchlist"
        )
    return title, msg


def send_pushover(
    regime: RegimeState,
    expressions: list[OptionsExpression],
    qual_results: list[QualificationResult],
    chop_count: int,
    run_dt: datetime,
) -> tuple[bool, Optional[str]]:
    """
    Send Pushover notification. Returns (sent, error_message).
    Silently skips if credentials not configured.
    """
    user_key  = os.environ.get("PUSHOVER_USER_KEY", "")
    api_token = os.environ.get("PUSHOVER_API_KEY", "")

    if not user_key or not api_token:
        logger.info("Pushover skipped — PUSHOVER_USER_KEY or PUSHOVER_API_KEY not set")
        return False, "credentials not configured"

    title, message = _pushover_message(regime, expressions, qual_results, chop_count, run_dt)

    try:
        resp = requests.post(
            _PUSHOVER_URL,
            data={
                "token":   api_token,
                "user":    user_key,
                "title":   title,
                "message": message,
                "sound":   "none" if len(expressions) == 0 else "pushover",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == 1:
            logger.info("Pushover sent: %s", title)
            return True, None
        else:
            err = str(data.get("errors", "unknown"))
            logger.warning("Pushover API error: %s", err)
            return False, err

    except Exception as exc:
        logger.warning("Pushover failed: %s", exc)
        return False, str(exc)
