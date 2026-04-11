"""
Intraday regime monitor — Layers 1–5 only.

Run via:  python -m signal_forge.run_intraday

Checks for regime shifts and VIX spikes vs the last committed state.
Sends Pushover only when a trigger fires AND the same alert type has not
been sent within the last 90 minutes.

State persisted in logs/intraday_state.json (committed to git between runs).
Appends a lightweight record to logs/audit.jsonl on every run.
Exits 0 always — intraday failures are logged, not fatal.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("signal_forge.run_intraday")

_STATE_PATH = Path("logs/intraday_state.json")
_AUDIT_PATH = Path("logs/audit.jsonl")
_DEDUP_MINUTES = 90

# Trigger thresholds
_VIX_SPIKE_THRESHOLD = 0.20   # VIX single-interval change > +20%

# Alert types for dedup tracking
ALERT_CHAOTIC           = "chaotic"
ALERT_REGIME_TO_RISK_ON = "regime_flip_risk_on"
ALERT_REGIME_TO_RISK_OFF= "regime_flip_risk_off"
ALERT_VIX_SPIKE         = "vix_spike"


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    if _STATE_PATH.exists():
        try:
            return json.loads(_STATE_PATH.read_text())
        except Exception as exc:
            logger.warning("State load failed: %s — using defaults", exc)
    return {
        "last_regime":     None,
        "last_vix":        None,
        "last_alert_type": None,
        "last_alert_utc":  None,
        "last_run_utc":    None,
    }


def _save_state(state: dict) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def _is_deduped(state: dict, alert_type: str, now: datetime) -> bool:
    """Return True if this alert type was already sent within the dedup window."""
    if state.get("last_alert_type") != alert_type:
        return False
    last_str = state.get("last_alert_utc")
    if not last_str:
        return False
    try:
        last_dt = datetime.fromisoformat(last_str)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        return (now - last_dt) < timedelta(minutes=_DEDUP_MINUTES)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Trigger detection
# ---------------------------------------------------------------------------

def _detect_triggers(
    current_regime: str,
    vix_change: float,
    last_regime: Optional[str],
) -> list[str]:
    """Return list of triggered alert types (may be empty)."""
    triggers: list[str] = []

    # Trigger 1: CHAOTIC
    if current_regime == "CHAOTIC":
        triggers.append(ALERT_CHAOTIC)
        return triggers  # CHAOTIC overrides all others

    # Trigger 2: regime flip RISK_ON ↔ RISK_OFF
    if last_regime is not None:
        flip_to_on  = last_regime == "RISK_OFF" and current_regime == "RISK_ON"
        flip_to_off = last_regime == "RISK_ON"  and current_regime == "RISK_OFF"
        if flip_to_on:
            triggers.append(ALERT_REGIME_TO_RISK_ON)
        if flip_to_off:
            triggers.append(ALERT_REGIME_TO_RISK_OFF)

    # Trigger 3: VIX single-interval spike > 20%
    if vix_change > _VIX_SPIKE_THRESHOLD:
        triggers.append(ALERT_VIX_SPIKE)

    return triggers


# ---------------------------------------------------------------------------
# Pushover message for intraday alert
# ---------------------------------------------------------------------------

def _build_pushover_payload(
    alert_type: str,
    regime_state,
    run_dt: datetime,
) -> tuple[str, str]:
    """Return (title, message) for a triggered intraday alert."""
    date_str = run_dt.strftime("%Y-%m-%d %H:%M UTC")

    if alert_type == ALERT_CHAOTIC:
        title   = f"SF ALERT | CHAOTIC — {run_dt.strftime('%H:%M UTC')}"
        message = (
            f"Regime: CHAOTIC (VIX +{regime_state.vix_change:.1%})\n"
            f"VIX: {regime_state.vix_level:.2f} | STAY FLAT"
        )
    elif alert_type == ALERT_REGIME_TO_RISK_ON:
        title   = f"SF ALERT | RISK_ON flip — {run_dt.strftime('%H:%M UTC')}"
        message = (
            f"Regime shifted to RISK_ON\n"
            f"Posture: {regime_state.posture} | Conf: {regime_state.confidence:.0%}\n"
            f"VIX: {regime_state.vix_level:.2f}"
        )
    elif alert_type == ALERT_REGIME_TO_RISK_OFF:
        title   = f"SF ALERT | RISK_OFF flip — {run_dt.strftime('%H:%M UTC')}"
        message = (
            f"Regime shifted to RISK_OFF\n"
            f"Posture: {regime_state.posture} | Conf: {regime_state.confidence:.0%}\n"
            f"VIX: {regime_state.vix_level:.2f}"
        )
    else:  # VIX spike
        title   = f"SF ALERT | VIX spike — {run_dt.strftime('%H:%M UTC')}"
        message = (
            f"VIX spike: {regime_state.vix_change:+.1%} intraday\n"
            f"VIX: {regime_state.vix_level:.2f} | {regime_state.regime}"
        )

    return title, message


def _send_pushover_alert(title: str, message: str) -> tuple[bool, Optional[str]]:
    import os
    import requests

    user_key  = os.environ.get("PUSHOVER_USER_KEY", "")
    api_token = os.environ.get("PUSHOVER_API_KEY", "")
    if not user_key or not api_token:
        logger.info("Pushover skipped — credentials not configured")
        return False, "credentials not configured"

    try:
        resp = requests.post(
            "https://api.pushover.net/1/messages.json",
            data={"token": api_token, "user": user_key,
                  "title": title, "message": message, "sound": "siren"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == 1:
            logger.info("Pushover sent: %s", title)
            return True, None
        err = str(data.get("errors", "unknown"))
        return False, err
    except Exception as exc:
        logger.warning("Pushover failed: %s", exc)
        return False, str(exc)


# ---------------------------------------------------------------------------
# Lightweight audit append
# ---------------------------------------------------------------------------

def _append_audit(run_id: str, run_dt: datetime, regime_state, alert_fired: Optional[str],
                  pushed: bool, elapsed: float) -> None:
    record = {
        "run_id":       run_id,
        "run_type":     "intraday",
        "timestamp_utc": run_dt.isoformat(),
        "regime":       regime_state.regime,
        "posture":      regime_state.posture,
        "confidence":   round(regime_state.confidence, 4),
        "vix_level":    regime_state.vix_level,
        "vix_change":   round(regime_state.vix_change, 6),
        "alert_fired":  alert_fired,
        "pushover_sent": pushed,
        "elapsed_seconds": round(elapsed, 2),
    }
    _AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _AUDIT_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True, default=str) + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    run_dt  = datetime.now(tz=timezone.utc)
    t_start = time.monotonic()
    import uuid
    run_id = str(uuid.uuid4())

    logger.info("Intraday run %s  %s", run_id[:8], run_dt.strftime("%H:%M UTC"))

    # ── L1–L3 ───────────────────────────────────────────────────────────
    try:
        from signal_forge.ingestion import fetch_all
        from signal_forge.normalization import normalize_all
        from signal_forge.validation import PipelineHaltError, validate_all

        raw     = fetch_all()
        normed  = normalize_all(raw)
        results = validate_all(normed)
    except Exception as exc:
        logger.error("Ingest/validate failed: %s", exc)
        _append_audit(run_id, run_dt,
                      type("R", (), {"regime":"UNKNOWN","posture":"UNKNOWN","confidence":0.0,
                                     "vix_level":0.0,"vix_change":0.0})(),
                      None, False, time.monotonic() - t_start)
        return 0  # non-fatal — intraday runs are best-effort

    # ── L5: regime ───────────────────────────────────────────────────────
    from signal_forge.regime import classify_regime, from_validation_results
    quotes = from_validation_results(results)
    regime = classify_regime(quotes)

    logger.info(
        "Regime: %s | Posture: %s | Conf: %.0f%% | VIX: %.2f (%+.2f%%)",
        regime.regime, regime.posture, regime.confidence * 100,
        regime.vix_level, regime.vix_change * 100,
    )

    # ── State & trigger detection ────────────────────────────────────────
    state = _load_state()
    last_regime = state.get("last_regime")
    triggers    = _detect_triggers(regime.regime, regime.vix_change, last_regime)

    alert_fired: Optional[str] = None
    pushed = False

    if triggers:
        logger.info("Triggers detected: %s", triggers)
        for alert_type in triggers:
            if _is_deduped(state, alert_type, run_dt):
                logger.info("Alert %s deduped (within %dm window)", alert_type, _DEDUP_MINUTES)
                continue
            # Fire this alert
            title, message = _build_pushover_payload(alert_type, regime, run_dt)
            pushed, push_err = _send_pushover_alert(title, message)
            alert_fired = alert_type
            # Update dedup state for this alert type
            state["last_alert_type"] = alert_type
            state["last_alert_utc"]  = run_dt.isoformat()
            logger.info("Alert fired: %s | Pushover: %s", alert_type, "sent" if pushed else push_err)
            break  # fire at most one alert per run (highest priority wins)
    else:
        logger.info("No triggers — monitoring only")

    # ── Update state ─────────────────────────────────────────────────────
    state["last_regime"]  = regime.regime
    state["last_vix"]     = regime.vix_level
    state["last_run_utc"] = run_dt.isoformat()
    _save_state(state)

    # ── Audit ─────────────────────────────────────────────────────────────
    _append_audit(run_id, run_dt, regime, alert_fired, pushed, time.monotonic() - t_start)

    return 0


if __name__ == "__main__":
    sys.exit(main())
