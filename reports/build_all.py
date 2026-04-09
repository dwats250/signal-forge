#!/usr/bin/env python3
"""Static site builder for Signal Forge report output."""

from __future__ import annotations

import json
import os
import shutil
from html import escape
from pathlib import Path

from reports import morning_edge, sunday_report
from reports.build_logging import append_report_log, generated_line, report_timestamp
from reports.design_system import shared_design_system_css
from reports.morning_healthcheck import (
    build_cli_summary,
    build_morning_healthcheck_summary,
    write_healthcheck_outputs,
)
from reports.report_lifecycle import vancouver_date_str

ROOT_DIR = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT_DIR / "_site"


def _fallback_report_data() -> dict:
    return {
        "generated_line": generated_line(),
        "state_summary": {
            "market_posture": "Mixed",
            "market_quality": "Mixed",
        },
        "no_setups": True,
    }


def _copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def _load_cached_data(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    data = payload.get("data")
    return data if isinstance(data, dict) else {}


def _change(entry: dict | None) -> float | None:
    if not entry:
        return None
    value = entry.get("day_chg")
    return value if isinstance(value, (int, float)) else None


def _arrow(change: float | None) -> str:
    if change is None:
        return "→"
    if change > 0:
        return "↑"
    if change < 0:
        return "↓"
    return "→"


def _price(entry: dict | None) -> float | None:
    if not entry:
        return None
    value = entry.get("price")
    return value if isinstance(value, (int, float)) else None


def _equity_strength(market_data: dict) -> bool:
    spy_chg = _change(market_data.get("SPY"))
    qqq_chg = _change(market_data.get("QQQ"))
    return (
        isinstance(spy_chg, (int, float))
        and spy_chg > 0.5
    ) or (
        isinstance(qqq_chg, (int, float))
        and qqq_chg > 0.7
    )


def _equity_weakness(market_data: dict) -> bool:
    spy_chg = _change(market_data.get("SPY"))
    qqq_chg = _change(market_data.get("QQQ"))
    return (
        isinstance(spy_chg, (int, float))
        and spy_chg <= 0.1
    ) and (
        isinstance(qqq_chg, (int, float))
        and qqq_chg <= 0.1
    )


def _regime_state(report_data: dict, market_data: dict) -> tuple[str, str]:
    state_summary = report_data.get("state_summary", {})
    posture = state_summary.get("market_posture", "Mixed")
    quality = state_summary.get("market_quality", "Mixed")
    us10y = _price(market_data.get("US10Y"))
    spy_chg = _change(market_data.get("SPY"))

    if posture == "Bullish" and quality == "Calm":
        return "Risk On", "positive"
    if posture == "Bearish":
        return "Risk Off", "negative"
    if quality == "Fragile" or (isinstance(us10y, (int, float)) and us10y >= 4.2):
        return "Range-bound -> Defensive bias", "warning"
    if isinstance(spy_chg, (int, float)) and spy_chg > 0:
        return "Range-bound -> Constructive bias", "neutral"
    return "Range-bound", "neutral"


def _driver_text(market_data: dict) -> str:
    wti_chg = _change(market_data.get("WTI"))
    us10y_chg = _change(market_data.get("US10Y"))
    dxy_chg = _change(market_data.get("DXY"))
    vix_chg = _change(market_data.get("VIX"))
    us10y = _price(market_data.get("US10Y"))
    dxy = _price(market_data.get("DXY"))

    if isinstance(us10y, (int, float)) and us10y >= 4.3:
        return "US10Y holding above 4.3% keeps risk pinned"
    if isinstance(us10y_chg, (int, float)) and us10y_chg > 0.4:
        return "Rising yields are capping risk appetite"
    if isinstance(dxy, (int, float)) and dxy >= 100.5:
        return "Firm dollar is leaning against cyclicals and metals"
    if isinstance(dxy_chg, (int, float)) and dxy_chg > 0.2:
        return "Dollar strength is tightening financial conditions"
    if isinstance(wti_chg, (int, float)) and wti_chg > 0.4:
        return "Oil strength is carrying energy leadership"
    if isinstance(wti_chg, (int, float)) and wti_chg < -0.4:
        return "Oil pullback is weakening energy leadership"
    if isinstance(vix_chg, (int, float)) and abs(vix_chg) >= 1.0:
        return "Falling VIX is easing stress, not confirming momentum" if vix_chg < 0 else "Rising VIX is lifting execution risk"
    if isinstance(us10y_chg, (int, float)) and us10y_chg < -0.4:
        return "Yields are easing, but risk has not broken free"
    return "Rates remain the primary trading constraint"


def _confidence_text(report_data: dict, market_data: dict) -> str:
    quality = report_data.get("state_summary", {}).get("market_quality", "Mixed")
    vix = market_data.get("VIX", {}).get("price")
    if quality == "Calm" and isinstance(vix, (int, float)) and vix < 16:
        return "High"
    if quality == "Fragile" and isinstance(vix, (int, float)) and vix >= 28:
        return "Low"
    return "Medium"


def _execution_posture(report_data: dict, market_data: dict) -> tuple[str, str, str]:
    quality = report_data.get("state_summary", {}).get("market_quality", "Mixed")
    no_setups = report_data.get("no_setups", True)
    wti_chg = _change(market_data.get("WTI"))
    gold_chg = _change(market_data.get("GOLD"))
    qqq_chg = _change(market_data.get("QQQ"))
    us10y = _price(market_data.get("US10Y"))
    vix = _price(market_data.get("VIX"))

    if quality == "Fragile" and no_setups and isinstance(vix, (int, float)) and vix >= 24:
        posture = "No trade"
    elif quality == "Fragile" and no_setups:
        posture = "Defensive"
    elif not no_setups and quality == "Calm":
        posture = "Aggressive"
    else:
        posture = "Selective"

    if posture == "No trade":
        focus = "Stand down until yields or volatility break the current choke point"
    elif posture == "Defensive":
        if isinstance(us10y, (int, float)) and us10y >= 4.3:
            focus = "Trade smaller and shorter-term until yields roll over"
        else:
            focus = "Protect capital and avoid conviction while cross-asset signals stay noisy"
    elif posture == "Aggressive":
        focus = "Press confirmed setups while volatility stays contained"
    elif isinstance(us10y, (int, float)) and us10y >= 4.3:
        focus = "Short-term trades only until yields break trend"
    elif isinstance(wti_chg, (int, float)) and wti_chg > 0.3:
        focus = "Lean into energy strength and avoid weak metals"
    elif isinstance(qqq_chg, (int, float)) and qqq_chg > 0.2:
        focus = "Favor growth follow-through only if rates stay contained"
    elif isinstance(gold_chg, (int, float)) and gold_chg < 0:
        focus = "Avoid fading metals weakness until dollar and yields soften"
    else:
        focus = "Wait for clearer alignment before adding index beta"

    tone = "negative" if posture == "Defensive" else "positive" if posture == "Aggressive" else "neutral"
    if posture == "No trade":
        tone = "negative"
    return posture, focus, tone


def _trigger_text(market_data: dict) -> str:
    us10y = _price(market_data.get("US10Y"))
    us10y_chg = _change(market_data.get("US10Y"))
    dxy = _price(market_data.get("DXY"))
    dxy_chg = _change(market_data.get("DXY"))
    wti_chg = _change(market_data.get("WTI"))
    vix_chg = _change(market_data.get("VIX"))

    if isinstance(us10y, (int, float)) and us10y >= 4.3:
        return "Sustained US10Y below 4.2% would reopen broader risk-on upside"
    if isinstance(us10y_chg, (int, float)) and us10y_chg > 0.4:
        return "A clear reversal lower in yields would ease the main pressure on risk"
    if isinstance(dxy, (int, float)) and dxy >= 100.5:
        return "A DXY breakdown would give equities and metals more room to expand"
    if isinstance(dxy_chg, (int, float)) and dxy_chg > 0.2:
        return "Dollar weakness would loosen the current cross-asset constraint"
    if isinstance(wti_chg, (int, float)) and abs(wti_chg) >= 0.4:
        return "Oil stability with contained yields would reset the sector leadership read"
    if isinstance(vix_chg, (int, float)) and vix_chg > 1.0:
        return "Falling VIX would be needed to relax the current defensive bias"
    return "A clean break lower in yields would shift the current range-bound read"


def _invalidation_text(market_data: dict) -> str:
    us10y = _price(market_data.get("US10Y"))
    us10y_chg = _change(market_data.get("US10Y"))
    dxy_chg = _change(market_data.get("DXY"))
    wti_chg = _change(market_data.get("WTI"))
    vix_chg = _change(market_data.get("VIX"))
    spy_chg = _change(market_data.get("SPY"))
    qqq_chg = _change(market_data.get("QQQ"))

    equity_strength = (
        isinstance(spy_chg, (int, float))
        and spy_chg > 0.5
    ) or (
        isinstance(qqq_chg, (int, float))
        and qqq_chg > 0.7
    )

    if isinstance(us10y, (int, float)) and us10y >= 4.3:
        return "Equities breaking higher despite firm yields would invalidate the current range-bound read"
    if isinstance(us10y_chg, (int, float)) and us10y_chg > 0.4:
        return "Risk assets rallying through higher yields would prove the current constraint is weaker than assumed"
    if isinstance(dxy_chg, (int, float)) and dxy_chg > 0.2:
        return "Dollar weakness without equity expansion would signal a more fragile tape than assumed"
    if isinstance(wti_chg, (int, float)) and abs(wti_chg) >= 0.4:
        return "Oil moving hard without confirming sector follow-through would contradict the current leadership read"
    if isinstance(vix_chg, (int, float)) and vix_chg < -1.0:
        return "Falling VIX with no equity follow-through would show risk appetite is still impaired"
    if equity_strength:
        return "A strong equity rally without cleaner cross-asset alignment would force a reassessment of the current regime logic"
    return "Cross-asset strength without yield relief would mean the current regime read is wrong"


def _drift_signal(report_data: dict, market_data: dict) -> tuple[str, str, str]:
    quality = report_data.get("state_summary", {}).get("market_quality", "Mixed")
    us10y = _price(market_data.get("US10Y"))
    us10y_chg = _change(market_data.get("US10Y"))
    dxy_chg = _change(market_data.get("DXY"))
    wti_chg = _change(market_data.get("WTI"))
    vix_chg = _change(market_data.get("VIX"))

    equity_strength = _equity_strength(market_data)
    equity_weakness = _equity_weakness(market_data)
    divergences: list[str] = []

    if (
        (isinstance(us10y, (int, float)) and us10y >= 4.3)
        or (isinstance(us10y_chg, (int, float)) and us10y_chg > 0.4)
    ) and equity_strength:
        divergences.append("equities holding up despite restrictive yields")

    if isinstance(dxy_chg, (int, float)) and dxy_chg < -0.2 and equity_weakness:
        divergences.append("dollar easing without broader risk expansion")

    if (
        isinstance(wti_chg, (int, float))
        and abs(wti_chg) >= 0.4
        and (
            (wti_chg > 0 and equity_weakness)
            or (wti_chg < 0 and equity_strength)
        )
    ):
        divergences.append("oil leadership is diverging from broader risk tone")

    if isinstance(vix_chg, (int, float)) and vix_chg < -1.0 and equity_weakness:
        divergences.append("volatility is easing without market follow-through")

    if len(divergences) >= 2:
        return "Building", f"{divergences[0]}; {divergences[1]}", "negative"
    if len(divergences) == 1:
        return "Emerging", divergences[0], "warning"
    if quality == "Fragile":
        return "Stable", "regime drivers intact, but tape quality still needs respect", "neutral"
    return "Stable", "regime drivers intact", "neutral"


def _position_bias(report_data: dict, market_data: dict) -> dict:
    quality = report_data.get("state_summary", {}).get("market_quality", "Mixed")
    no_setups = report_data.get("no_setups", True)
    us10y = _price(market_data.get("US10Y"))
    us10y_chg = _change(market_data.get("US10Y"))
    dxy_chg = _change(market_data.get("DXY"))
    wti_chg = _change(market_data.get("WTI"))
    vix = _price(market_data.get("VIX"))
    spy_chg = _change(market_data.get("SPY"))
    qqq_chg = _change(market_data.get("QQQ"))

    equity_strength = (
        isinstance(spy_chg, (int, float)) and spy_chg > 0.4
    ) or (
        isinstance(qqq_chg, (int, float)) and qqq_chg > 0.5
    )
    yields_heavy = (
        (isinstance(us10y, (int, float)) and us10y >= 4.3)
        or (isinstance(us10y_chg, (int, float)) and us10y_chg > 0.4)
    )
    dollar_heavy = isinstance(dxy_chg, (int, float)) and dxy_chg > 0.2
    vol_heavy = isinstance(vix, (int, float)) and vix >= 24

    if equity_strength and isinstance(us10y_chg, (int, float)) and us10y_chg < -0.4 and not dollar_heavy:
        return {
            "bias": "Pro-risk",
            "expression": "Buy dips and lean into momentum while rates stay supportive",
            "avoid": "Fading strength too early",
        }

    if yields_heavy or vol_heavy or (quality == "Fragile" and no_setups):
        expression = "Fade strength, keep trades short-term, and stay selective on entries"
        if isinstance(wti_chg, (int, float)) and wti_chg > 0.3:
            expression = "Trade short-term around strength and favor energy over broad beta"
        return {
            "bias": "Neutral -> slight defensive tilt",
            "expression": expression,
            "avoid": "High-conviction directional positioning",
        }

    if dollar_heavy:
        return {
            "bias": "Neutral",
            "expression": "Lean into relative strength only and keep broad beta exposure tight",
            "avoid": "Chasing weak macro follow-through",
        }

    return {
        "bias": "Neutral",
        "expression": "Trade ranges tactically until cross-asset confirmation improves",
        "avoid": "Forcing breakout trades without driver alignment",
    }


def _what_matters_now(report_data: dict, market_data: dict, sunday_data: dict) -> list[str]:
    bullets: list[str] = []
    wti_chg = _change(market_data.get("WTI"))
    us10y_chg = _change(market_data.get("US10Y"))
    vix_chg = _change(market_data.get("VIX"))
    gold_chg = _change(market_data.get("GOLD"))
    btc_chg = _change(market_data.get("BTC"))
    dxy_chg = _change(market_data.get("DXY"))
    sunday_wti = sunday_data.get("WTI", {}).get("week_chg")
    us10y = _price(market_data.get("US10Y"))

    if isinstance(us10y, (int, float)) and us10y >= 4.3:
        bullets.append("US10Y holding above 4.3% -> keeps pressure on risk assets")
    elif isinstance(us10y_chg, (int, float)):
        if us10y_chg > 0.4:
            bullets.append("Yields pressing higher -> caps duration-sensitive upside")
        elif us10y_chg < -0.4:
            bullets.append("Yields easing -> relieves some pressure on growth, but does not confirm a clean breakout")

    if len(bullets) < 3 and isinstance(dxy_chg, (int, float)) and dxy_chg > 0.2:
        bullets.append("DXY firming -> keeps a headwind on metals and broad risk")

    if len(bullets) < 3 and isinstance(wti_chg, (int, float)) and wti_chg > 0.3:
        if isinstance(sunday_wti, (int, float)) and sunday_wti > 5:
            bullets.append("Oil holding weekly momentum -> keeps energy leadership in play")
        else:
            bullets.append("Oil pushing higher -> supporting energy equities")
    elif len(bullets) < 3 and isinstance(wti_chg, (int, float)) and wti_chg < -0.3:
        bullets.append("Oil pullback -> weakens energy leadership")

    if len(bullets) < 3 and isinstance(vix_chg, (int, float)):
        if vix_chg < -1.0:
            bullets.append("VIX falling -> no panic, but no momentum confirmation either")
        elif vix_chg > 1.0:
            bullets.append("VIX rising -> argues for smaller size and tighter entries")
    if len(bullets) < 3 and isinstance(gold_chg, (int, float)) and gold_chg < 0:
        bullets.append("Gold slipping -> safe-haven demand is not bailing out weak risk tone")
    if len(bullets) < 3 and isinstance(btc_chg, (int, float)) and btc_chg > 1.0:
        bullets.append("BTC firming -> speculative appetite is stabilizing at the margin")

    return bullets[:3]


def _key_signals(market_data: dict) -> str:
    parts = [
        ("DXY", "DXY"),
        ("US10Y", "US10Y"),
        ("VIX", "VIX"),
        ("WTI", "Oil"),
        ("GOLD", "Gold"),
        ("BTC", "BTC"),
    ]
    return " | ".join(
        f"{label} {_arrow(_change(market_data.get(symbol)))}"
        for symbol, label in parts
    )


def _highlight_assets(text: str) -> str:
    highlighted = escape(text)
    for asset in ("US10Y", "VIX", "DXY", "Oil", "Gold", "BTC", "Yields"):
        highlighted = highlighted.replace(
            asset,
            f'<span class="asset-strong">{asset}</span>',
        )
    return highlighted


def _highlight_drift_reason(text: str) -> str:
    highlighted = escape(text)
    for phrase in (
        "drivers intact",
        "tape quality",
        "restrictive yields",
        "broader risk expansion",
        "market follow-through",
        "broader risk tone",
    ):
        highlighted = highlighted.replace(phrase, f"<strong>{phrase}</strong>")
    return highlighted


def _render_signals_strip(market_data: dict) -> str:
    parts = [
        ("DXY", "DXY"),
        ("US10Y", "US10Y"),
        ("VIX", "VIX"),
        ("WTI", "Oil"),
        ("GOLD", "Gold"),
        ("BTC", "BTC"),
    ]
    rendered: list[str] = []
    for symbol, label in parts:
        arrow = _arrow(_change(market_data.get(symbol)))
        arrow_cls = "flat" if arrow == "→" else "up" if arrow == "↑" else "down"
        rendered.append(
            f'<span class="signal-pill"><span class="signal-label">{escape(label)}</span> '
            f'<span class="signal-arrow {arrow_cls}">{arrow}</span></span>'
        )
    return " ".join(rendered)


def _build_dashboard_data(report_data: dict) -> dict:
    market_data = _load_cached_data(morning_edge.MARKET_CACHE_PATH)
    sunday_data = _load_cached_data(sunday_report.MARKET_CACHE_PATH)
    regime, regime_tone = _regime_state(report_data, market_data)
    drift_state, drift_reason, drift_tone = _drift_signal(report_data, market_data)
    posture, focus, posture_tone = _execution_posture(report_data, market_data)
    position_bias = _position_bias(report_data, market_data)
    return {
        "generated_line": report_data.get("generated_line", ""),
        "risk_value": regime,
        "driver_value": _driver_text(market_data),
        "confidence_value": _confidence_text(report_data, market_data),
        "regime_tone": regime_tone,
        "trigger_value": _trigger_text(market_data),
        "invalidation_value": _invalidation_text(market_data),
        "drift_state": drift_state,
        "drift_reason": drift_reason,
        "drift_value": f"{drift_state} — {drift_reason}",
        "drift_tone": drift_tone,
        "posture_value": posture,
        "focus_value": focus,
        "posture_tone": posture_tone,
        "bias_value": position_bias["bias"],
        "expression_value": position_bias["expression"],
        "avoid_value": position_bias["avoid"],
        "what_matters_now": _what_matters_now(report_data, market_data, sunday_data),
        "signals_line": _key_signals(market_data),
        "signals_html": _render_signals_strip(market_data),
    }


def _render_dashboard_html(dashboard: dict) -> str:
    what_matters_items = "\n".join(
        f"        <li>{_highlight_assets(item)}</li>"
        for item in dashboard["what_matters_now"]
    )
    design_system_css = shared_design_system_css(page_max="1200px")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Signal Forge Dashboard</title>
<style>
  {design_system_css}
  .page {{ gap: 14px; }}
  .header {{
    align-items: baseline;
    gap: 16px;
  }}
  .ts {{
    font-size: 0.88rem;
    color: var(--text-muted);
    letter-spacing: 0.04em;
  }}
  .prominent {{
    padding-top: 16px;
    padding-bottom: 16px;
    background: linear-gradient(180deg, rgba(91, 151, 229, 0.12), rgba(29, 35, 48, 0.96));
  }}
  .command-block {{
    display: grid;
    gap: 12px;
  }}
  .command-pair {{
    display: grid;
    gap: 2px;
  }}
  .command-label {{
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-muted);
  }}
  .command-value {{
    font-size: clamp(1rem, 0.94rem + 0.42vw, 1.18rem);
    font-weight: 750;
    letter-spacing: 0.01em;
    line-height: 1.35;
    color: var(--text);
  }}
  .prominent .command-value:first-of-type {{
    text-shadow: 0 0 18px rgba(91, 151, 229, 0.12);
  }}
  .bias-card {{
    background: linear-gradient(180deg, rgba(230, 180, 74, 0.07), rgba(29, 35, 48, 0.92));
  }}
  .drift-card {{
    background: linear-gradient(180deg, rgba(91, 151, 229, 0.045), rgba(23, 27, 35, 1));
    border-color: rgba(91, 151, 229, 0.14);
  }}
  .asset-strong {{
    font-weight: 800;
    color: #F7FAFF;
  }}
  .what-matters {{
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}
  .what-matters li {{
    color: var(--text);
    padding-left: 16px;
    position: relative;
    font-size: 0.96rem;
  }}
  .what-matters li::before {{
    content: '•';
    position: absolute;
    left: 0;
    color: var(--accent-gold);
  }}
  .signals-strip {{
    font-size: 0.96rem;
    font-weight: 700;
    color: var(--text);
    letter-spacing: 0.02em;
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }}
  .signal-pill {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(255, 255, 255, 0.03);
  }}
  .signal-label {{
    color: var(--text-muted);
    font-size: 0.84rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }}
  .signal-arrow {{
    font-size: 0.98rem;
    font-weight: 900;
  }}
  .signal-arrow.up {{
    color: var(--accent-green);
    text-shadow: 0 0 14px rgba(63, 211, 122, 0.2);
  }}
  .signal-arrow.down {{
    color: var(--accent-red);
    text-shadow: 0 0 14px rgba(240, 107, 107, 0.2);
  }}
  .signal-arrow.flat {{
    color: var(--text-muted);
  }}
  .reports-grid {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
  }}
  @media (max-width: 760px) {{
    .page {{ gap: 12px; }}
    .reports-grid {{ grid-template-columns: 1fr; }}
    .command-block {{ gap: 10px; }}
    .command-value, .signals-strip {{ font-size: 0.94rem; }}
  }}
</style>
</head>
<body>
  <main class="page">
    <header class="header">
      <h1>Signal <span>Forge</span></h1>
      <span class="ts">{escape(dashboard["generated_line"])}</span>
    </header>

    <section class="card card-emphasis prominent tone-{dashboard["regime_tone"]}">
      <div class="command-block">
        <div class="command-pair">
          <div class="command-label">Risk</div>
          <div class="command-value">{escape(dashboard["risk_value"])}</div>
        </div>
        <div class="command-pair">
          <div class="command-label">Driver</div>
          <div class="command-value">{escape(dashboard["driver_value"])}</div>
        </div>
        <div class="command-pair">
          <div class="command-label">Confidence</div>
          <div class="command-value">{escape(dashboard["confidence_value"])}</div>
        </div>
      </div>
    </section>

    <section class="card tone-{dashboard["regime_tone"]}">
      <div class="command-block">
        <div class="command-pair">
          <div class="command-label">Trigger</div>
          <div class="command-value">{escape(dashboard["trigger_value"])}</div>
        </div>
      </div>
    </section>

    <section class="card tone-{dashboard["regime_tone"]}">
      <div class="command-block">
        <div class="command-pair">
          <div class="command-label">Invalidation</div>
          <div class="command-value">{escape(dashboard["invalidation_value"])}</div>
        </div>
      </div>
    </section>

    <section class="card drift-card tone-{dashboard["drift_tone"]}">
      <div class="command-block">
        <div class="command-pair">
          <div class="command-label">Drift</div>
          <div class="command-value">{escape(dashboard["drift_state"])}</div>
        </div>
        <div class="command-pair">
          <div class="command-value">{escape(dashboard["drift_reason"])}</div>
        </div>
      </div>
    </section>

    <section class="card tone-{dashboard["posture_tone"]}">
      <div class="command-block">
        <div class="command-pair">
          <div class="command-label">Posture</div>
          <div class="command-value">{escape(dashboard["posture_value"])}</div>
        </div>
        <div class="command-pair">
          <div class="command-label">Focus</div>
          <div class="command-value">{escape(dashboard["focus_value"])}</div>
        </div>
      </div>
    </section>

    <section class="card tone-{dashboard["posture_tone"]} bias-card card-bias">
      <div class="command-block">
        <div class="command-pair">
          <div class="command-label">Bias</div>
          <div class="command-value">{escape(dashboard["bias_value"])}</div>
        </div>
        <div class="command-pair">
          <div class="command-label">Expression</div>
          <div class="command-value">{escape(dashboard["expression_value"])}</div>
        </div>
        <div class="command-pair">
          <div class="command-label">Avoid</div>
          <div class="command-value">{escape(dashboard["avoid_value"])}</div>
        </div>
      </div>
    </section>

    <section class="card">
      <div class="card-title">What Matters Now</div>
      <ul class="what-matters">
{what_matters_items}
      </ul>
    </section>

    <section class="card">
      <div class="card-title">Key Signals Strip</div>
      <div class="signals-strip">{dashboard["signals_html"]}</div>
    </section>

    <section class="card">
      <div class="card-title">Latest Reports</div>
      <div class="reports-grid">
        <article class="card report-card">
          <div class="report-label">Sunday Report</div>
          <div class="report-copy">Weekly macro regime, themes, risks, and execution posture</div>
          <div class="report-meta">Latest stable output</div>
          <div class="report-actions">
            <a class="report-link primary" href="latest_sunday.html">Open HTML</a>
            <a class="report-link secondary" href="latest_sunday.pdf">Open PDF</a>
          </div>
        </article>
        <article class="card report-card">
          <div class="report-label">Premarket Report</div>
          <div class="report-copy">Daily market posture, what matters today, and execution context</div>
          <div class="report-meta">Latest stable output</div>
          <div class="report-actions">
            <a class="report-link primary" href="latest_premarket.html">Open HTML</a>
            <a class="report-link secondary" href="latest_premarket.pdf">Open PDF</a>
          </div>
        </article>
      </div>
    </section>
  </main>
</body>
</html>
"""


def _write_archive_index(report_data: dict) -> Path:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    archive_dir = SITE_DIR / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    index_path = archive_dir / "index.html"
    archive_files = sorted(morning_edge.ARCHIVE_DIR.glob("*.html"), reverse=True)
    items = "\n".join(
        f'      <li><a href="{path.name}">{path.stem}</a></li>'
        for path in archive_files
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Morning Macro Edge Archives</title>
<style>
  :root {{
    --bg: #0B0B0F;
    --bg-card: #111117;
    --bg-card2: #16161E;
    --border: #1E1E2A;
    --accent: #3B82F6;
    --accent-gold: #F59E0B;
    --text: #EAEAF0;
    --text-muted: #8A8A9D;
    --page-max: 1200px;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font: 500 16px/1.6 Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  }}
  .page {{
    width: min(100%, 840px);
    margin: 0 auto;
    padding: 40px 24px 56px;
  }}
  .eyebrow {{
    font-size: 12px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 8px;
  }}
  h1 {{
    margin: 0 0 10px;
    font-size: clamp(2rem, 1.7rem + 1vw, 2.4rem);
    line-height: 1.1;
  }}
  .subtitle {{
    color: var(--text-muted);
    font-size: 1rem;
    margin-bottom: 22px;
  }}
  .card {{
    background: linear-gradient(180deg, var(--bg-card2), var(--bg-card));
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 22px;
  }}
  .archive-list {{
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}
  .archive-list a {{
    display: block;
    text-decoration: none;
    color: inherit;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
    background: rgba(255, 255, 255, 0.01);
  }}
  .archive-list a:hover {{
    border-color: rgba(59, 130, 246, 0.45);
  }}
  .archive-date {{
    font-size: 1rem;
    font-weight: 600;
  }}
  .archive-copy {{
    color: var(--text-muted);
    font-size: 0.9rem;
    margin-top: 4px;
  }}
  .meta {{
    margin-top: 24px;
    color: var(--text-muted);
    font-size: 0.9rem;
  }}
  .back-link {{
    color: var(--accent);
    text-decoration: none;
  }}
</style>
</head>
<body>
  <main class="page">
    <div class="eyebrow">Signal Forge</div>
    <h1>Morning Macro Edge Archives</h1>
    <p class="subtitle">Dated report snapshots.</p>
    <section class="card">
      <ul class="archive-list">
{items}
      </ul>
    </section>
    <div class="meta"><a class="back-link" href="../">Back to latest report</a> · {report_data['generated_line']}</div>
  </main>
</body>
</html>
"""
    index_path.write_text(html, encoding="utf-8")
    return index_path


def build_site() -> Path:
    print("=" * 60)
    print("Signal Forge — Static Site Build")
    print("=" * 60)

    offline = not bool(os.environ.get("ANTHROPIC_API_KEY"))
    if offline:
        print("ANTHROPIC_API_KEY not set — using stub narrative.")
    failed_components: list[str] = []
    stage_statuses = {
        "sunday_report": "failure",
        "morning_edge": "failure",
        "dashboard": "failure",
    }
    append_report_log("build_all.run", "start", "manual_or_scheduled_build_started")

    sunday_data: dict | None = None
    try:
        sunday_data = sunday_report.run_report(offline=offline, with_pdf=True)
        stage_failures = sunday_data.get("_failed_stages", []) if isinstance(sunday_data, dict) else []
        failed_components.extend(stage_failures)
        append_report_log("build_all.sunday_report", "success")
        stage_statuses["sunday_report"] = "success"
    except Exception as exc:
        failed_components.append("sunday_report")
        append_report_log("build_all.sunday_report", "failure", f"exception={type(exc).__name__}: {exc}")

    report_data: dict = _fallback_report_data()
    try:
        report_data = morning_edge.run_report(offline=offline, with_pdf=True)
        failed_components.extend(report_data.get("_failed_stages", []))
        append_report_log("build_all.morning_edge", "success")
        stage_statuses["morning_edge"] = "success"
    except Exception as exc:
        failed_components.append("morning_edge")
        append_report_log("build_all.morning_edge", "failure", f"exception={type(exc).__name__}: {exc}")

    html_path = morning_edge.LIVE_HTML_PATH

    archive_matches = sorted(morning_edge.ARCHIVE_DIR.glob(f"premarket_{vancouver_date_str()}" + "*.html"))
    archive_src = archive_matches[-1] if archive_matches else None
    site_archive_dir = SITE_DIR / "archive"
    site_archive_dir.mkdir(parents=True, exist_ok=True)
    try:
        dashboard_data = _build_dashboard_data(report_data)
        (SITE_DIR / "index.html").write_text(_render_dashboard_html(dashboard_data), encoding="utf-8")
        if html_path.exists():
            shutil.copy2(html_path, SITE_DIR / "morning_edge.html")
        _copy_if_exists(morning_edge.LATEST_HTML_PATH, SITE_DIR / "latest_premarket.html")
        _copy_if_exists(morning_edge.LATEST_PDF_PATH, SITE_DIR / "latest_premarket.pdf")
        _copy_if_exists(sunday_report.LATEST_HTML_PATH, SITE_DIR / "latest_sunday.html")
        _copy_if_exists(sunday_report.LATEST_PDF_PATH, SITE_DIR / "latest_sunday.pdf")
        if archive_src is not None:
            shutil.copy2(archive_src, site_archive_dir / archive_src.name)
        _write_archive_index(report_data)
        append_report_log("build_all.dashboard", "success")
        stage_statuses["dashboard"] = "success"
    except Exception as exc:
        failed_components.append("dashboard")
        append_report_log("build_all.dashboard", "failure", f"exception={type(exc).__name__}: {exc}")

    print(f"Site index: {SITE_DIR / 'index.html'}")
    print(f"Latest report: {SITE_DIR / 'morning_edge.html'}")
    if archive_src is not None:
        print(f"Archive copy: {site_archive_dir / archive_src.name}")
    print(f"Archive index: {site_archive_dir / 'index.html'}")
    healthcheck_summary = build_morning_healthcheck_summary(
        stage_statuses=stage_statuses,
        report_data=report_data,
    )
    report_data["healthcheck"] = healthcheck_summary
    try:
        if "macro_bar" in report_data and "thesis" in report_data:
            morning_edge.render_html(report_data, out_path=morning_edge.LIVE_HTML_PATH)
            morning_edge.render_html(report_data, out_path=morning_edge.LATEST_HTML_PATH)
            if html_path.exists():
                shutil.copy2(html_path, SITE_DIR / "morning_edge.html")
            _copy_if_exists(morning_edge.LATEST_HTML_PATH, SITE_DIR / "latest_premarket.html")
    except Exception as exc:
        failed_components.append("healthcheck_render")
        append_report_log("build_all.healthcheck_render", "failure", f"exception={type(exc).__name__}: {exc}")
    write_healthcheck_outputs(healthcheck_summary)
    unique_failures = sorted(set(failed_components))
    if unique_failures:
        summary = ", ".join(unique_failures)
        print(f"REPORT BUILD PARTIAL — {summary}")
        append_report_log("build_all.run", "partial", summary)
    else:
        success_line = f"REPORT BUILD SUCCESS — {report_timestamp()}"
        print(success_line)
        append_report_log("build_all.run", "success", success_line)
    print(build_cli_summary(healthcheck_summary))
    return SITE_DIR


def main() -> None:
    build_site()


if __name__ == "__main__":
    main()
