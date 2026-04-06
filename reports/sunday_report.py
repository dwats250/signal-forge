#!/usr/bin/env python3
"""Sunday Macro Report — weekly directional bias, regime, and trade themes.

Entry point: python -m reports.sunday_report
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

import anthropic
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape
from reports.design_system import shared_design_system_css
from reports.report_lifecycle import promote_report_artifact
from signal_forge.data.unified_data import (
    DATA_SOURCE_UNAVAILABLE,
    DEFAULT_PROVIDER_SYMBOLS,
    UnifiedMarketDataClient,
)

# ── Paths ──────────────────────────────────────────────────────────────────

REPORTS_DIR = Path(__file__).parent
TEMPLATE_DIR = REPORTS_DIR / "templates"
OUTPUT_DIR = REPORTS_DIR / "output"
ARCHIVE_DIR = REPORTS_DIR / "archive" / "sunday"
MARKET_CACHE_PATH = OUTPUT_DIR / "sunday_market.latest.json"
LIVE_HTML_PATH = OUTPUT_DIR / "sunday_report.html"
LIVE_PDF_PATH = OUTPUT_DIR / "sunday_report.pdf"
LATEST_HTML_PATH = OUTPUT_DIR / "latest_sunday.html"
LATEST_PDF_PATH = OUTPUT_DIR / "latest_sunday.pdf"

# ── Tickers ────────────────────────────────────────────────────────────────

TICKER_KEYS: list[str] = [
    "DXY", "US10Y", "US2Y", "VIX", "USDJPY",
    "WTI", "BRENT",
    "GOLD", "SILVER",
    "SPY", "QQQ", "IWM", "BTC",
    "XLE", "OXY", "XOM",
    "GDX", "SLV",
]

YIELD_TICKERS: set[str] = {"US10Y", "US2Y"}

# Extended provider symbol maps — adds Sunday-specific tickers not in defaults.
PROVIDER_SYMBOLS: dict[str, dict[str, str]] = {
    "yfinance": {
        **DEFAULT_PROVIDER_SYMBOLS["yfinance"],
        "US2Y":   "^IRX",    # 13-week T-bill — directional proxy for short-end
        "USDJPY": "JPY=X",
        "IWM":    "IWM",
        "XOM":    "XOM",
        "SLV":    "SLV",
        "BRENT":  "BZ=F",
    },
    "fmp": {
        **DEFAULT_PROVIDER_SYMBOLS["fmp"],
        "IWM": "IWM",
        "XOM": "XOM",
        "SLV": "SLV",
    },
    "stooq": {
        **DEFAULT_PROVIDER_SYMBOLS["stooq"],
        "IWM": "iwm.us",
        "XOM": "xom.us",
        "SLV": "slv.us",
    },
}

# ── Ticker highlight ───────────────────────────────────────────────────────

_TICKER_NAMES: frozenset[str] = frozenset(TICKER_KEYS)
_TICKER_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in sorted(_TICKER_NAMES, key=len, reverse=True)) + r")\b"
)


def _highlight_tickers_filter(text: str) -> Markup:
    if not text:
        return Markup("")
    safe = str(escape(text))
    highlighted = _TICKER_PATTERN.sub(r'<span class="ticker-inline">\1</span>', safe)
    return Markup(highlighted)


# ── Week label ─────────────────────────────────────────────────────────────

def _week_label(now: datetime) -> tuple[str, str]:
    """Return (week_of_str, date_range_str) for the upcoming Mon–Fri trading week."""
    days_to_monday = (7 - now.weekday()) % 7
    if days_to_monday == 0:
        days_to_monday = 7
    monday = (now + timedelta(days=days_to_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    friday = monday + timedelta(days=4)
    week_of = monday.strftime("%B %-d, %Y")
    date_range = f"{monday.strftime('%b %-d')} – {friday.strftime('%b %-d, %Y')}"
    return week_of, date_range


# ── Stub market data ───────────────────────────────────────────────────────

def build_stub_market_data() -> dict:
    """Deterministic fallback snapshot for offline/static builds."""
    return {
        "DXY":    {"price": 104.12, "day_chg": -0.3, "week_chg": -1.1, "formatted": "104.12",   "is_yield": False},
        "US10Y":  {"price": 4.21,   "day_chg":  3.0, "week_chg":  8.0, "formatted": "4.21%",    "is_yield": True},
        "US2Y":   {"price": 4.82,   "day_chg":  2.0, "week_chg":  5.0, "formatted": "4.82%",    "is_yield": True},
        "VIX":    {"price": 18.4,   "day_chg":  4.2, "week_chg": 12.0, "formatted": "18.4",     "is_yield": False},
        "USDJPY": {"price": 151.42, "day_chg":  0.4, "week_chg":  1.2, "formatted": "¥151.42",  "is_yield": False},
        "WTI":    {"price": 82.35,  "day_chg":  1.1, "week_chg":  2.8, "formatted": "$82.35",   "is_yield": False},
        "BRENT":  {"price": 85.90,  "day_chg":  1.0, "week_chg":  2.5, "formatted": "$85.90",   "is_yield": False},
        "GOLD":   {"price": 2320.0, "day_chg":  0.6, "week_chg":  2.1, "formatted": "$2,320",   "is_yield": False},
        "SILVER": {"price": 27.15,  "day_chg":  0.9, "week_chg":  3.0, "formatted": "$27.15",   "is_yield": False},
        "SPY":    {"price": 520.0,  "day_chg":  0.4, "week_chg":  0.8, "formatted": "$520.00",  "is_yield": False},
        "QQQ":    {"price": 443.0,  "day_chg":  0.5, "week_chg":  1.1, "formatted": "$443.00",  "is_yield": False},
        "IWM":    {"price": 198.5,  "day_chg": -0.2, "week_chg": -0.6, "formatted": "$198.50",  "is_yield": False},
        "BTC":    {"price": 68500,  "day_chg":  1.8, "week_chg":  5.2, "formatted": "$68,500",  "is_yield": False},
        "XLE":    {"price": 96.10,  "day_chg":  0.8, "week_chg":  2.2, "formatted": "$96.10",   "is_yield": False},
        "OXY":    {"price": 67.80,  "day_chg":  1.0, "week_chg":  2.7, "formatted": "$67.80",   "is_yield": False},
        "XOM":    {"price": 119.40, "day_chg":  0.7, "week_chg":  1.9, "formatted": "$119.40",  "is_yield": False},
        "GDX":    {"price": 34.20,  "day_chg":  0.6, "week_chg":  2.0, "formatted": "$34.20",   "is_yield": False},
        "SLV":    {"price": 24.80,  "day_chg":  0.8, "week_chg":  2.8, "formatted": "$24.80",   "is_yield": False},
    }


# ── Data fetch ─────────────────────────────────────────────────────────────

def _format_price(value: float, ticker: str) -> str:
    if ticker in YIELD_TICKERS:
        return f"{value:.2f}%"
    if ticker == "VIX":
        return f"{value:.1f}"
    if ticker == "DXY":
        return f"{value:.2f}"
    if ticker == "USDJPY":
        return f"¥{value:.2f}"
    if ticker == "BTC":
        return f"${value:,.0f}"
    return f"${value:.2f}"


def fetch_market_data() -> dict:
    print("Fetching market data...")
    client = UnifiedMarketDataClient(provider_symbols=PROVIDER_SYMBOLS)
    outcome = client.fetch_entries(
        TICKER_KEYS,
        cache_path=MARKET_CACHE_PATH,
        fallback_builder=build_stub_market_data,
        formatter=_format_price,
        yield_tickers=YIELD_TICKERS,
    )
    if outcome.fallback_used:
        if outcome.source == "cache":
            print(f"  Warning: {DATA_SOURCE_UNAVAILABLE}: using cached data from {MARKET_CACHE_PATH}.")
        else:
            print(f"  Warning: {DATA_SOURCE_UNAVAILABLE}: using stub data.")
    if not outcome.fallback_used:
        _save_cache(outcome.data)
    return outcome.data


def _save_cache(data: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "cached_at": datetime.now(ZoneInfo("America/Vancouver")).isoformat(),
        "source": "yfinance",
        "data": data,
    }
    MARKET_CACHE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# ── Derived metrics ────────────────────────────────────────────────────────

def _compute_yield_curve(md: dict) -> dict:
    """2s/10s spread derived from US10Y and US2Y prices."""
    us10y = md.get("US10Y", {}).get("price")
    us2y = md.get("US2Y", {}).get("price")
    if us10y is None or us2y is None:
        return {"spread": None, "label": "N/A", "shape": "UNKNOWN", "color": "neutral"}
    spread = round(us10y - us2y, 2)
    sign = "+" if spread >= 0 else ""
    if spread >= 0.5:
        shape, color = "STEEP", "positive"
    elif spread >= 0:
        shape, color = "NORMAL", "neutral"
    elif spread >= -0.25:
        shape, color = "FLAT", "neutral"
    else:
        shape, color = "INVERTED", "negative"
    return {"spread": spread, "label": f"{sign}{spread:.2f}%", "shape": shape, "color": color}


# ── Macro snapshot ─────────────────────────────────────────────────────────

def _chg_str(val: float | None, is_yield: bool = False) -> str:
    if val is None:
        return "N/A"
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.0f}bps" if is_yield else f"{sign}{val:.1f}%"


def build_macro_snapshot(md: dict) -> list[dict]:
    spec = [
        ("DXY",    "DXY",        False),
        ("US10Y",  "US10Y",      True),
        ("US2Y",   "US2Y ~prx",  True),
        ("VIX",    "VIX",        False),
        ("USDJPY", "USDJPY",     False),
        ("WTI",    "WTI",        False),
        ("GOLD",   "XAU",        False),
        ("SILVER", "XAG",        False),
        ("SPY",    "SPY",        False),
        ("BTC",    "BTC",        False),
    ]
    rows = []
    for key, label, is_yield in spec:
        d = md.get(key, {"price": None, "week_chg": None, "formatted": "N/A", "is_yield": is_yield})
        wchg = d.get("week_chg")
        rows.append({
            "label": label,
            "value": d.get("formatted", "N/A"),
            "weekly_chg": _chg_str(wchg, is_yield),
            "direction": "up" if wchg is not None and wchg > 0 else "down" if wchg is not None and wchg < 0 else "flat",
        })
    return rows


# ── Narrative schema ───────────────────────────────────────────────────────

SUNDAY_SCHEMA = {
    "regime": "RISK_ON | MIXED | RISK_OFF",
    "regime_driver": "OIL-DRIVEN | RATES-DRIVEN | DOLLAR-DRIVEN | LIQUIDITY-DRIVEN | MIXED",
    "regime_confidence": "HIGH | MEDIUM | LOW",
    "regime_bullets": ["2-3 short bullet strings explaining the regime call"],
    "quality": "CLEAN | MIXED | CHAOTIC",
    "posture": "TRADE AGGRESSIVELY | TRADE SELECTIVELY | REDUCE SIZE | NO TRADE",
    "quality_signals": [
        {
            "label": "Volatility Stability | Cross-Asset Alignment | Trend Agreement | Chop Detection",
            "signal": "short assessment string",
            "tone": "positive | negative | neutral",
        }
    ],
    "cross_asset_bullets": ["4-6 strings interpreting cross-asset relationships"],
    "what_matters": [
        {
            "title": "string — e.g. CPI (Wednesday)",
            "why": "string — why it matters for the week",
            "implication": "string — trade implication or timing guidance",
        }
    ],
    "events": [
        {
            "date": "string — e.g. Mon Apr 7",
            "event": "string",
            "impact": "HIGH | MEDIUM",
            "note": "string — 1-line execution guidance",
        }
    ],
    "themes": [
        {
            "title": "string — e.g. Energy continuation on supply tightness",
            "bias": "Bullish | Bearish | Neutral",
            "logic": "string — supporting macro logic, 1-2 sentences",
            "invalidates_if": "string — specific condition that kills this theme",
        }
    ],
    "energy_paragraph": "string — XLE trend, OXY behavior, leverage ETF context, directional bias",
    "energy_action": "string — short directive for energy this week",
    "metals_paragraph": "string — gold vs real yields, silver participation, miners vs underlying",
    "metals_action": "string — short directive for metals this week",
    "playbook": ["3-6 directive instruction strings — imperative, concrete"],
    "primary_drivers": ["string — driver 1", "string — driver 2"],
    "key_risk": "string — single biggest threat to the week thesis",
}


# ── Stub narrative ─────────────────────────────────────────────────────────

def _stub_narrative(md: dict) -> dict:
    def p(k: str) -> str:
        return md.get(k, {}).get("formatted", "N/A")

    return {
        "regime": "MIXED",
        "regime_driver": "RATES-DRIVEN",
        "regime_confidence": "MEDIUM",
        "regime_bullets": [
            f"US10Y at {p('US10Y')} is the dominant constraint — duration-sensitive risk remains under pressure.",
            f"DXY at {p('DXY')} is holding elevated, capping metals and limiting international equity upside.",
            f"VIX at {p('VIX')} — not in stress territory, but cross-asset alignment is poor.",
        ],
        "quality": "MIXED",
        "posture": "TRADE SELECTIVELY",
        "quality_signals": [
            {"label": "Volatility Stability",   "signal": f"VIX {p('VIX')} — elevated but not crisis-level", "tone": "neutral"},
            {"label": "Cross-Asset Alignment",  "signal": "Rates and equities diverging — no clean read",     "tone": "negative"},
            {"label": "Trend Agreement",         "signal": "Energy leading; metals and indices range-bound",   "tone": "neutral"},
            {"label": "Chop Detection",          "signal": "Index tape showing range compression",             "tone": "negative"},
        ],
        "cross_asset_bullets": [
            f"Dollar ({p('DXY')}) strength is the primary headwind for metals and international equities.",
            f"US10Y at {p('US10Y')} — rate expectations are keeping equity multiples compressed.",
            f"WTI ({p('WTI')}) holding above support; energy sector is the only clean trend on the board.",
            f"Gold ({p('GOLD')}) and silver ({p('SILVER')}) are range-bound — dollar is the primary constraint.",
            f"USDJPY at {p('USDJPY')} — carry unwind risk is elevated if US yields pull back materially.",
            f"VIX ({p('VIX')}) elevated — risk-on entry quality is poor; size down.",
        ],
        "what_matters": [
            {
                "title": "Federal Reserve Speakers",
                "why": "Rate path guidance directly moves DXY, yields, and risk appetite for the week.",
                "implication": "Avoid new positions before major Fed speeches — tone shock risk is high.",
            },
            {
                "title": "WTI Supply Picture",
                "why": f"Oil at {p('WTI')} needs supply-side confirmation to sustain the energy sector bid.",
                "implication": "Watch XLE and OXY for inventory-driven continuation or reversal signal.",
            },
            {
                "title": "Equity Index Trend Resolution",
                "why": "SPY and QQQ need to confirm direction — range compression is unsustainable.",
                "implication": "Wait for directional break before adding index beta. No anticipation.",
            },
        ],
        "events": [
            {
                "date": "TBD",
                "event": "Fed Speakers",
                "impact": "HIGH",
                "note": "Tone on rate path — significant DXY and yield mover.",
            },
            {
                "date": "TBD",
                "event": "Oil Inventories (EIA)",
                "impact": "MEDIUM",
                "note": "Surprise vs consensus drives WTI and XLE direction.",
            },
        ],
        "themes": [
            {
                "title": "Energy continuation on supply tightness",
                "bias": "Bullish",
                "logic": f"WTI at {p('WTI')} remains supported by OPEC discipline. XLE and OXY showing relative strength vs broader tape.",
                "invalidates_if": "WTI loses prior support level or DXY accelerates above 106.",
            },
            {
                "title": "Rates-driven equity multiple compression",
                "bias": "Bearish",
                "logic": f"US10Y at {p('US10Y')} continues to cap growth multiples. QQQ underperforming on duration sensitivity.",
                "invalidates_if": "US10Y breaks below 4.0% on a macro catalyst or Fed pivot signal.",
            },
            {
                "title": "Metals consolidation under strong dollar",
                "bias": "Neutral",
                "logic": f"Gold at {p('GOLD')} and silver at {p('SILVER')} are range-bound. Dollar strength is suppressing the upside.",
                "invalidates_if": "DXY breaks below 103 or Fed signals a dovish shift.",
            },
        ],
        "energy_paragraph": (
            f"XLE is maintaining relative strength with WTI at {p('WTI')} providing underlying support. "
            f"OXY at {p('OXY')} is tracking futures with normal beta — no dislocation. "
            f"Leverage ETFs (GUSH, UCO) viable for momentum continuation but require tight stops and defined risk."
        ),
        "energy_action": "Prioritize pullback entries in XLE and OXY — no chasing breakouts.",
        "metals_paragraph": (
            f"Gold at {p('GOLD')} is consolidating with real yields elevated and dollar strong. "
            f"Silver at {p('SILVER')} showing limited participation — gold/silver ratio is widening. "
            f"GDX at {p('GDX')} — miners are underperforming the metal, suggesting distribution pressure or hedging."
        ),
        "metals_action": "Avoid chasing metals until DXY shows a sustained break below 103.",
        "playbook": [
            "Prioritize pullback entries in energy — no chasing breakouts above resistance",
            "Avoid metals unless DXY weakens materially or real yields roll over",
            "Reduce index size until trend alignment improves across SPY, QQQ, IWM",
            "Favor spreads over outright directional calls in a mixed regime",
            "No new positions within 30 min of major macro events (Fed, CPI, NFP)",
            "Size down to 50% max while VIX remains above 18",
        ],
        "primary_drivers": [
            "Rates direction — US10Y is the regime pin",
            "Dollar strength — DXY is suppressing risk appetite",
        ],
        "key_risk": "Hawkish Fed surprise re-accelerating yields above 4.5% and triggering broad risk-off.",
    }


# ── Generate narrative ─────────────────────────────────────────────────────

def generate_narrative(md: dict, week_of: str) -> dict:
    print("Generating weekly narrative via Claude...")

    def fmt(k: str) -> str:
        d = md.get(k, {})
        if d.get("price") is None:
            return f"{k}: N/A"
        chg = d.get("week_chg", 0) or 0
        is_yield = d.get("is_yield", False)
        sign = "+" if chg >= 0 else ""
        chg_s = f"{sign}{chg:.0f}bps WoW" if is_yield else f"{sign}{chg:.1f}% WoW"
        return f"{k}: {d['formatted']} ({chg_s})"

    curve = _compute_yield_curve(md)
    data_summary = "\n".join([
        fmt("DXY"), fmt("US10Y"), fmt("US2Y"),
        f"2s/10s curve: {curve['label']} ({curve['shape']})",
        fmt("VIX"), fmt("USDJPY"),
        fmt("WTI"), fmt("BRENT"),
        fmt("GOLD"), fmt("SILVER"),
        fmt("SPY"), fmt("QQQ"), fmt("IWM"), fmt("BTC"),
        fmt("XLE"), fmt("OXY"), fmt("XOM"),
        fmt("GDX"), fmt("SLV"),
    ])

    prompt = f"""You are a professional macro trader writing a Sunday evening weekly report for the trading week of {week_of}.

MARKET DATA (Friday close / latest weekly):
{data_summary}

NOTE: US2Y is proxied by 13-week T-bill — use for directional yield curve context only.

Generate a structured JSON response matching this exact schema:
{json.dumps(SUNDAY_SCHEMA, indent=2)}

Rules:
- This is a FORWARD-LOOKING weekly report. Focus on what will drive the week ahead, not what already happened.
- regime: RISK_ON = equities up + vol falling + cross-asset aligned. RISK_OFF = equities down + vol rising + safe havens bid. MIXED = conflicting signals.
- quality: CLEAN = all major assets in clear trends. MIXED = some divergence. CHAOTIC = no directional clarity.
- posture: TRADE AGGRESSIVELY only when CLEAN + RISK_ON. NO TRADE only when CHAOTIC or extreme uncertainty.
- quality_signals: Include exactly 4 components — Volatility Stability, Cross-Asset Alignment, Trend Agreement, Chop Detection.
- what_matters: 3-5 items that will actually resolve uncertainty this week. No filler.
- events: List real, scheduled events for week of {week_of}. Include FOMC (if scheduled), CPI, NFP, major earnings if relevant. Do NOT fabricate events. If uncertain, list "TBD" for date.
- themes: 3-5 directional ideas grounded in the current data. Each needs a specific, testable invalidation condition.
- playbook: Directive, imperative. Concrete guidance. 3-6 items max.
- key_risk: Single most dangerous tail scenario for the week. Specific — not generic.

Return ONLY valid JSON. No markdown, no code blocks, no commentary."""

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  Warning: ANTHROPIC_API_KEY not set — using stub narrative.")
        return _stub_narrative(md)

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    return json.loads(raw)


# ── Report assembly ────────────────────────────────────────────────────────

def build_report_data(md: dict, narrative: dict, now: datetime) -> dict:
    week_of, date_range = _week_label(now)
    return {
        "week_of":       week_of,
        "date_range":    date_range,
        "generated_line": now.strftime("Generated %a %b %-d, %Y at %-I:%M %p %Z"),
        # Regime
        "regime":             narrative.get("regime", "MIXED"),
        "regime_driver":      narrative.get("regime_driver", "MIXED"),
        "regime_confidence":  narrative.get("regime_confidence", "LOW"),
        "regime_bullets":     narrative.get("regime_bullets", []),
        # Quality
        "quality":         narrative.get("quality", "MIXED"),
        "posture":         narrative.get("posture", "TRADE SELECTIVELY"),
        "quality_signals": narrative.get("quality_signals", []),
        # Snapshot
        "macro_snapshot": build_macro_snapshot(md),
        "yield_curve":    _compute_yield_curve(md),
        # Analysis
        "cross_asset_bullets": narrative.get("cross_asset_bullets", []),
        "what_matters":        narrative.get("what_matters", []),
        "events":              narrative.get("events", []),
        "themes":              narrative.get("themes", []),
        # Sectors
        "energy": {
            "xle": md.get("XLE", {}),
            "oxy": md.get("OXY", {}),
            "xom": md.get("XOM", {}),
            "wti": md.get("WTI", {}),
            "paragraph": narrative.get("energy_paragraph", ""),
            "action":    narrative.get("energy_action", ""),
        },
        "metals": {
            "gold":   md.get("GOLD", {}),
            "silver": md.get("SILVER", {}),
            "gdx":    md.get("GDX", {}),
            "slv":    md.get("SLV", {}),
            "paragraph": narrative.get("metals_paragraph", ""),
            "action":    narrative.get("metals_action", ""),
        },
        # Playbook + Summary
        "playbook":        narrative.get("playbook", []),
        "primary_drivers": narrative.get("primary_drivers", []),
        "key_risk":        narrative.get("key_risk", ""),
    }


# ── Rendering ──────────────────────────────────────────────────────────────

def render_html(report_data: dict, out_path: Path | None = None) -> Path:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    env.filters["highlight_tickers"] = _highlight_tickers_filter
    template = env.get_template("sunday_report.html")
    html_content = template.render(
        **report_data,
        design_system_css=shared_design_system_css(page_max="1200px"),
    )

    if out_path is None:
        out_path = LIVE_HTML_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_content, encoding="utf-8")

    return out_path


def render_pdf(html_path: Path, out_path: Path | None = None) -> Path:
    from weasyprint import HTML

    pdf_path = LIVE_PDF_PATH if out_path is None else out_path
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(filename=str(html_path)).write_pdf(str(pdf_path))
    return pdf_path


def run_report(*, offline: bool = False, with_pdf: bool = True) -> dict:
    print("=" * 60)
    print("Sunday Macro Report — Weekly Decision Framework")
    print("=" * 60)

    now = datetime.now(ZoneInfo("America/Vancouver"))
    week_of, date_range = _week_label(now)
    print(f"Week of: {date_range}")

    market_data = fetch_market_data()
    narrative = (
        _stub_narrative(market_data)
        if offline
        else generate_narrative(market_data, week_of)
    )
    report_data = build_report_data(market_data, narrative, now)

    with TemporaryDirectory(prefix="sunday-report-") as tmpdir:
        temp_dir = Path(tmpdir)
        html_temp_path = temp_dir / LIVE_HTML_PATH.name
        pdf_temp_path = temp_dir / LIVE_PDF_PATH.name

        try:
            render_html(report_data, out_path=html_temp_path)
        except Exception as exc:
            print(f"[FAIL] Sunday Report generation failed: {exc}")
            raise
        print(f"[OK] Generated Sunday Report HTML -> {html_temp_path}")

        pdf_generated = False
        if with_pdf:
            try:
                render_pdf(html_temp_path, out_path=pdf_temp_path)
            except Exception as exc:
                print(f"[FAIL] Sunday Report PDF generation failed: {exc}")
            else:
                pdf_generated = True
                print(f"[OK] Generated Sunday Report PDF -> {pdf_temp_path}")

        promote_report_artifact(
            report_label="Sunday Report HTML",
            live_path=LIVE_HTML_PATH,
            archive_dir=ARCHIVE_DIR,
            archive_prefix="sunday_report",
            temp_path=html_temp_path,
            latest_pointer_path=LATEST_HTML_PATH,
            now=now,
        )

        if pdf_generated:
            promote_report_artifact(
                report_label="Sunday Report PDF",
                live_path=LIVE_PDF_PATH,
                archive_dir=ARCHIVE_DIR,
                archive_prefix="sunday_report",
                temp_path=pdf_temp_path,
                latest_pointer_path=LATEST_PDF_PATH,
                now=now,
            )

    print("=" * 60)
    print(f"Regime: {report_data['regime']}  |  Quality: {report_data['quality']}  |  Posture: {report_data['posture']}")
    print("=" * 60)
    return report_data


# ── Main ───────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Sunday Macro Report generator")
    parser.add_argument("--offline", action="store_true", help="Skip Claude API, use stub narrative")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF rendering")
    args = parser.parse_args(argv)
    run_report(offline=args.offline, with_pdf=not args.no_pdf)


if __name__ == "__main__":
    main()
