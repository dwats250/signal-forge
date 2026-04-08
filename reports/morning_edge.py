#!/usr/bin/env python3
"""Morning Macro Edge — daily one-page macro + execution report."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

import anthropic
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape
from reports.build_logging import (
    append_confidence_score_log,
    append_data_source_log,
    append_report_log,
    generated_line,
    report_now,
)
from reports.design_system import shared_design_system_css
from reports.report_lifecycle import promote_report_artifact
from signal_forge.data.commodity_resolver import validate_price
from signal_forge.data.unified_data import (
    DATA_SOURCE_UNAVAILABLE,
    FetchOutcome,
    UnifiedMarketDataClient,
    compute_data_confidence,
    validate_data_point,
)

# ── Paths ──────────────────────────────────────────────────────────────────

REPORTS_DIR = Path(__file__).parent
TEMPLATE_DIR = REPORTS_DIR / "templates"
OUTPUT_DIR = REPORTS_DIR / "output"
ARCHIVE_DIR = REPORTS_DIR / "archive" / "daily"
MARKET_CACHE_PATH = OUTPUT_DIR / "market_data.latest.json"
LIVE_HTML_PATH = OUTPUT_DIR / "premarket.html"
LIVE_PDF_PATH = OUTPUT_DIR / "premarket.pdf"
LATEST_HTML_PATH = OUTPUT_DIR / "latest_premarket.html"
LATEST_PDF_PATH = OUTPUT_DIR / "latest_premarket.pdf"

# ── Ticker map ─────────────────────────────────────────────────────────────

TICKERS: dict[str, str] = {
    "DXY": "DX-Y.NYB",
    "US10Y": "^TNX",
    "WTI": "CL=F",
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "COPPER": "HG=F",
    "PLATINUM": "PL=F",
    "PALLADIUM": "PA=F",
    "SPY": "SPY",
    "QQQ": "QQQ",
    "BTC": "BTC-USD",
    "VIX": "^VIX",
    "XLE": "XLE",
    "OXY": "OXY",
    "GDX": "GDX",
    "NEM": "NEM",
    "WPM": "WPM",
    "TSLA": "TSLA",
    "MU": "MU",
}

YIELD_TICKERS = {"US10Y"}  # report change in bps, not pct
DATA_UNAVAILABLE_TEXT = "DATA UNAVAILABLE"
METALS_FALLBACK_TEXT = DATA_UNAVAILABLE_TEXT
INVENTORY_FALLBACK_TEXT = "Inventory data unavailable"
MARKET_VALIDATION_RANGES: dict[str, tuple[float, float]] = {
    "GOLD": (1000.0, 5500.0),
    "SILVER": (10.0, 100.0),
    "COPPER": (2.0, 8.0),
    "PLATINUM": (500.0, 2000.0),
    "PALLADIUM": (500.0, 2500.0),
    "WTI": (20.0, 200.0),
}
NARRATIVE_RETRY_ATTEMPTS = 2
# ── Ticker highlight filter ────────────────────────────────────────────────

_TICKER_NAMES: frozenset[str] = frozenset(TICKERS) | {"REAL10Y"}
_TICKER_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in sorted(_TICKER_NAMES, key=len, reverse=True)) + r")\b"
)


def _highlight_tickers_filter(text: str) -> Markup:
    """Wrap known ticker symbols in text with a highlight span. Safe for autoescape."""
    if not text:
        return Markup("")
    safe = str(escape(text))
    highlighted = _TICKER_PATTERN.sub(r'<span class="ticker-inline">\1</span>', safe)
    return Markup(highlighted)


# ── Data layer ─────────────────────────────────────────────────────────────

def build_stub_market_data() -> dict:
    """Deterministic fallback market snapshot for offline/static builds."""
    stub = {
        "DXY": {"price": 104.82, "day_chg": 0.3, "week_chg": 0.9, "formatted": "104.82", "is_yield": False},
        "US10Y": {"price": 4.21, "day_chg": 4.0, "week_chg": 11.0, "formatted": "4.21%", "is_yield": True},
        "WTI": {"price": 81.44, "day_chg": 1.1, "week_chg": 2.7, "formatted": "$81.44", "is_yield": False},
        "GOLD": {"price": 2318.20, "day_chg": 0.4, "week_chg": 1.8, "formatted": "$2318.20", "is_yield": False},
        "SILVER": {"price": 26.11, "day_chg": 0.6, "week_chg": 2.2, "formatted": "$26.11", "is_yield": False},
        "COPPER": {"price": 4.18, "day_chg": 0.9, "week_chg": 2.4, "formatted": "$4.18", "is_yield": False},
        "PLATINUM": {"price": 968.40, "day_chg": -0.2, "week_chg": 1.1, "formatted": "$968.40", "is_yield": False},
        "PALLADIUM": {"price": 1022.75, "day_chg": 0.3, "week_chg": 0.8, "formatted": "$1022.75", "is_yield": False},
        "SPY": {"price": 518.47, "day_chg": 0.5, "week_chg": 1.1, "formatted": "$518.47", "is_yield": False},
        "QQQ": {"price": 442.35, "day_chg": 0.7, "week_chg": 1.5, "formatted": "$442.35", "is_yield": False},
        "BTC": {"price": 68350.0, "day_chg": 1.2, "week_chg": 4.9, "formatted": "$68,350", "is_yield": False},
        "VIX": {"price": 14.8, "day_chg": -2.1, "week_chg": -5.0, "formatted": "14.8", "is_yield": False},
        "XLE": {"price": 95.42, "day_chg": 0.9, "week_chg": 2.1, "formatted": "$95.42", "is_yield": False},
        "OXY": {"price": 67.18, "day_chg": 1.0, "week_chg": 2.6, "formatted": "$67.18", "is_yield": False},
        "GDX": {"price": 33.72, "day_chg": 0.5, "week_chg": 1.6, "formatted": "$33.72", "is_yield": False},
        "NEM": {"price": 36.48, "day_chg": 0.4, "week_chg": 1.3, "formatted": "$36.48", "is_yield": False},
        "WPM": {"price": 47.26, "day_chg": 0.7, "week_chg": 1.9, "formatted": "$47.26", "is_yield": False},
        "TSLA": {"price": 171.63, "day_chg": -0.8, "week_chg": -1.4, "formatted": "$171.63", "is_yield": False},
        "MU": {"price": 123.54, "day_chg": 1.4, "week_chg": 3.2, "formatted": "$123.54", "is_yield": False},
    }
    stub["REAL10Y"] = {
        "price": 2.01,
        "day_chg": 4.0,
        "week_chg": 11.0,
        "formatted": "2.01%",
        "is_yield": True,
        "estimated": True,
    }
    return stub


def _cache_payload(data: dict, source: str = "yfinance") -> dict:
    now_vancouver = datetime.now(ZoneInfo("America/Vancouver"))
    return {
        "cached_at": now_vancouver.isoformat(),
        "source": source,
        "data": data,
    }


def save_market_data_cache(data: dict, source: str = "yfinance") -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MARKET_CACHE_PATH.write_text(
        json.dumps(_cache_payload(data, source=source), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def load_market_data_cache() -> dict | None:
    if not MARKET_CACHE_PATH.exists():
        return None
    try:
        payload = json.loads(MARKET_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  Warning: failed to read cached market data: {exc}")
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        print("  Warning: cached market data payload is malformed.")
        return None
    return data


def _missing_market_entry(*, is_yield: bool = False, estimated: bool = False, reason: str = DATA_UNAVAILABLE_TEXT) -> dict:
    entry = {
        "price": None,
        "day_chg": None,
        "week_chg": None,
        "formatted": reason,
        "is_yield": is_yield,
        "source_unavailable": True,
    }
    if estimated:
        entry["estimated"] = True
    return entry


def _invalidate_market_entry(name: str, entry: dict, *, reason: str) -> dict:
    invalid = _missing_market_entry(
        is_yield=entry.get("is_yield", False),
        estimated=entry.get("estimated", False),
        reason=DATA_UNAVAILABLE_TEXT,
    )
    invalid["validation_failed"] = True
    invalid["validation_reason"] = f"{name}: {reason}"
    return invalid


def _entry_price(entry: dict | None) -> float | None:
    if not isinstance(entry, dict):
        return None
    price = entry.get("price")
    return float(price) if isinstance(price, (int, float)) else None


def _build_market_entry_from_closes(closes: list[float], ticker: str) -> dict:
    current = float(closes[-1])
    prev = float(closes[-2])
    week_ago = float(closes[-6]) if len(closes) >= 6 else float(closes[0])
    day_chg = (current - prev) / prev * 100
    week_chg = (current - week_ago) / week_ago * 100
    return {
        "price": current,
        "day_chg": round(day_chg, 2),
        "week_chg": round(week_chg, 2),
        "formatted": _format_price(current, ticker),
        "is_yield": False,
    }


def _commodity_unavailable_entry(symbol: str, fallback_text: str) -> dict:
    invalid = _missing_market_entry(reason=fallback_text)
    invalid["validation_failed"] = True
    invalid["validation_reason"] = f"{symbol}: {fallback_text}"
    return invalid


def _cache_preserving_commodities(result: dict) -> dict:
    cache_ready = dict(result)
    cached = load_market_data_cache() or {}
    for symbol in ("GOLD", "WTI"):
        current = cache_ready.get(symbol)
        cached_entry = cached.get(symbol)
        current_price = _entry_price(current)
        if validate_price(symbol, current_price) and isinstance(current, dict) and not current.get("last_known_good", False):
            continue
        cached_price = _entry_price(cached_entry)
        if validate_price(symbol, cached_price):
            cache_ready[symbol] = dict(cached_entry)
    return cache_ready


def _sanitize_market_data(result: dict) -> dict:
    for ticker, (low, high) in MARKET_VALIDATION_RANGES.items():
        entry = result.get(ticker)
        if not isinstance(entry, dict):
            continue
        price = entry.get("price")
        if price is None:
            continue
        if low <= price <= high:
            continue
        print(
            f"  Warning: {ticker} price {price:.2f} is outside expected range [{low:.0f}, {high:.0f}]. "
            "Marking entry unavailable."
        )
        result[ticker] = _invalidate_market_entry(
            ticker,
            entry,
            reason=f"Validation failed: price outside expected range [{low:.0f}, {high:.0f}]",
        )
    return result


def _build_metals_context(md: dict) -> dict:
    gold = md.get("GOLD", _missing_market_entry())
    silver = md.get("SILVER", _missing_market_entry())
    copper = md.get("COPPER", _missing_market_entry())
    platinum = md.get("PLATINUM", _missing_market_entry())
    palladium = md.get("PALLADIUM", _missing_market_entry())
    real10y = md.get("REAL10Y", _missing_market_entry(is_yield=True, estimated=True))

    ratio = None
    if gold.get("price") and silver.get("price"):
        ratio = round(gold["price"] / silver["price"], 2)

    inventory_lines = [
        f"Gold / silver ratio: {ratio:.2f}" if ratio is not None else "Gold / silver ratio: Unavailable",
        f"COMEX silver front month: {silver.get('formatted', METALS_FALLBACK_TEXT)}"
        if silver.get("price") is not None
        else "COMEX silver front month: Source unavailable",
        "Shanghai silver reference: Shanghai data not yet integrated",
        "Warehouse / exchange inventory: Inventory data coming soon",
    ]

    return {
        "gold": gold,
        "silver": silver,
        "copper": copper,
        "platinum": platinum,
        "palladium": palladium,
        "real10y": real10y,
        "gold_silver_ratio": f"{ratio:.2f}" if ratio is not None else "Unavailable",
        "cards": [
            {"label": "Gold", "entry": gold},
            {"label": "Silver", "entry": silver},
            {"label": "Copper", "entry": copper},
            {"label": "Platinum", "entry": platinum},
            {"label": "Palladium", "entry": palladium},
        ],
        "inventory_lines": inventory_lines,
    }


def _format_numeric_delta(name: str, delta: float | None) -> str:
    if delta is None:
        return "Unavailable"
    return f"{delta:+.2f}"


def _plumbing_item(name: str, label: str, entry: dict) -> dict:
    price = entry.get("price")
    day_chg = entry.get("day_chg")
    badge_text, badge_tone = _source_badge(entry)
    if price is None or day_chg is None:
        return {
            "label": label,
            "value": entry.get("formatted", METALS_FALLBACK_TEXT),
            "absolute_change": "Unavailable",
            "percent_change": "Unavailable",
            "direction": "flat",
            "badge_text": badge_text,
            "badge_tone": badge_tone,
        }

    if entry.get("is_yield"):
        absolute_change = f"{day_chg / 100:+.2f} pts"
        percent_change = f"{day_chg:+.0f}bps"
    else:
        prev = price / (1 + (day_chg / 100))
        absolute_change = _format_numeric_delta(name, price - prev)
        percent_change = f"{day_chg:+.2f}%"

    return {
        "label": label,
        "value": entry.get("formatted", METALS_FALLBACK_TEXT),
        "absolute_change": absolute_change,
        "percent_change": percent_change,
        "direction": "up" if day_chg > 0 else "down" if day_chg < 0 else "flat",
        "badge_text": badge_text,
        "badge_tone": badge_tone,
    }


def _build_financial_plumbing(md: dict) -> list[dict]:
    return [
        _plumbing_item("DXY", "DXY", md.get("DXY", _missing_market_entry())),
        _plumbing_item("US10Y", "US 10Y", md.get("US10Y", _missing_market_entry(is_yield=True))),
        _plumbing_item("VIX", "VIX", md.get("VIX", _missing_market_entry())),
        _plumbing_item("WTI", "Oil", md.get("WTI", _missing_market_entry())),
        _plumbing_item("GOLD", "Gold", md.get("GOLD", _missing_market_entry())),
        _plumbing_item("SILVER", "Silver", md.get("SILVER", _missing_market_entry())),
    ]


def _source_badge(entry: dict | None) -> tuple[str, str]:
    if not isinstance(entry, dict):
        return "DATA UNAVAILABLE", "red"
    source = str(entry.get("source", "unavailable")).lower()
    if source == "stooq":
        return "FALLBACK SOURCE (STOOQ)", "yellow"
    if source == "cache":
        return "CACHED VALUE", "yellow"
    if source == "fmp":
        return "PRIMARY: FMP", "green"
    if source == "stub":
        return "DEGRADED STUB", "red"
    return "DATA UNAVAILABLE", "red"


def _confidence_badge(score: int) -> tuple[str, str]:
    if score > 85:
        return f"DATA CONFIDENCE {score}/100", "green"
    if score >= 70:
        return f"DATA CONFIDENCE {score}/100", "yellow"
    return f"DATA CONFIDENCE {score}/100", "red"


def _build_state_summary(md: dict, narrative: dict) -> dict:
    thesis = narrative.get("thesis", "")
    thesis_lower = thesis.lower()
    vix = md.get("VIX", {}).get("price")
    meta = md.get("_meta", {})
    confidence_score = int(meta.get("confidence_score", compute_data_confidence(md)))

    if "bull" in thesis_lower:
        posture = "Bullish"
    elif "bear" in thesis_lower:
        posture = "Bearish"
    elif "range" in thesis_lower:
        posture = "Range-bound"
    else:
        posture = "Mixed"

    if vix is None:
        quality = "Mixed"
    elif vix < 16:
        quality = "Calm"
    elif vix < 22:
        quality = "Balanced"
    else:
        quality = "Fragile"

    if confidence_score < 70:
        execution_bias = "Blocked"
    elif confidence_score <= 85:
        execution_bias = "High Score Only"
    else:
        execution_bias = "Selective" if narrative.get("no_setups", True) else "Actionable"

    posture_color = "positive" if posture == "Bullish" else "negative" if posture == "Bearish" else "neutral"
    quality_color = "positive" if quality == "Calm" else "negative" if quality == "Fragile" else "neutral"
    bias_color = "negative" if execution_bias == "Blocked" else "neutral" if execution_bias == "High Score Only" else "positive" if execution_bias == "Actionable" else "neutral"

    return {
        "market_posture": posture,
        "market_quality": quality,
        "execution_bias": execution_bias,
        "data_confidence": confidence_score,
        "posture_color": posture_color,
        "quality_color": quality_color,
        "bias_color": bias_color,
    }

def _format_price(value: float, ticker: str) -> str:
    if ticker in ("GOLD", "SILVER", "COPPER", "PLATINUM", "PALLADIUM", "WTI", "OXY", "GDX", "NEM", "WPM", "TSLA", "MU"):
        return f"${value:.2f}"
    if ticker in ("SPY", "QQQ"):
        return f"${value:.2f}"
    if ticker == "BTC":
        return f"${value:,.0f}"
    if ticker == "DXY":
        return f"{value:.2f}"
    if ticker in YIELD_TICKERS:
        return f"{value:.2f}%"
    if ticker == "VIX":
        return f"{value:.1f}"
    return f"{value:.2f}"


def fetch_market_data() -> dict:
    """Fetch live market data for all tracked tickers."""
    print("Fetching market data...")
    try:
        client = UnifiedMarketDataClient()
        outcome = client.fetch_entries(
            list(TICKERS),
            cache_path=MARKET_CACHE_PATH,
            fallback_builder=build_stub_market_data,
            formatter=_format_price,
            yield_tickers=YIELD_TICKERS,
        )
    except Exception as exc:
        print(f"  Warning: live market data fetch failed unexpectedly ({type(exc).__name__}).")
        append_report_log("morning_edge.data_fetch", "failure", f"exception={type(exc).__name__}: {exc}")
        cached = load_market_data_cache()
        if cached is not None:
            outcome = FetchOutcome(cached, "cache", True, DATA_SOURCE_UNAVAILABLE)
        else:
            outcome = FetchOutcome(build_stub_market_data(), "stub", True, DATA_SOURCE_UNAVAILABLE)

    if outcome.fallback_used:
        if outcome.source == "cache":
            print(f"  Warning: {DATA_SOURCE_UNAVAILABLE}: provider data unavailable.")
            print(f"  Using cached market data from {MARKET_CACHE_PATH}.")
        else:
            print(f"  Warning: {DATA_SOURCE_UNAVAILABLE}: provider data unavailable.")
            print("  Falling back to deterministic stub market data for this build.")

    result = _sanitize_market_data(outcome.data)
    meta = result.setdefault("_meta", {})
    meta["confidence_score"] = int(meta.get("confidence_score", compute_data_confidence(result)))
    meta["critical_missing"] = [ticker for ticker in ("DXY", "US10Y", "VIX") if not bool(result.get(ticker, {}).get("valid"))]
    meta["fail_safe_no_trade"] = len(meta["critical_missing"]) == 3

    # Estimate REAL10Y: US10Y minus approximate 10Y breakeven inflation (~2.2%)
    us10y = result.get("US10Y", {}).get("price")
    if us10y is not None:
        real10y_est = round(us10y - 2.2, 2)
        us10y_day = result["US10Y"].get("day_chg", 0)
        result["REAL10Y"] = {
            "price": real10y_est,
            "day_chg": us10y_day,  # moves ~1:1 with nominal in short term
            "week_chg": result["US10Y"].get("week_chg", 0),
            "formatted": f"{real10y_est:.2f}%",
            "is_yield": True,
            "estimated": True,
            "source": result["US10Y"].get("source", "unavailable"),
            "timestamp": result["US10Y"].get("timestamp", ""),
            "valid": bool(result["US10Y"].get("valid")),
        }
    else:
        result["REAL10Y"] = _missing_market_entry(is_yield=True, estimated=True)

    # ── Commodity audit ────────────────────────────────────────────────────
    wti_entry = result.get("WTI", {})
    wti_price = wti_entry.get("price")
    if wti_price is not None:
        print(f"  [audit] WTI   price: {wti_price:.2f} USD  (source: {wti_entry.get('source', 'unknown')})")
    else:
        print("  Warning: WTI price is unavailable after validation. No live oil value will be rendered.")

    gold_entry = result.get("GOLD", {})
    silver_entry = result.get("SILVER", {})
    gold_price = gold_entry.get("price")
    silver_price = silver_entry.get("price")
    if gold_price is not None:
        print(
            f"  [audit] GOLD  price: {gold_price:.2f} USD  "
            f"(source: {gold_entry.get('source', 'unknown')})"
        )
        print(f"  [audit] SILVER price: {silver_price:.2f} USD  (symbol: SI=F, source: yfinance)" if silver_price else "  [audit] SILVER price: unavailable")
        if silver_price and silver_price > 0:
            ratio = gold_price / silver_price
            print(f"  [audit] Gold/Silver ratio: {ratio:.1f}")
            if not (25.0 <= ratio <= 150.0):
                print(f"  Warning: Gold/Silver ratio {ratio:.1f} is anomalous — check GC=F vs SI=F data integrity.")
    else:
        print("  Warning: GOLD price is unavailable after FMP-backed validation. No live gold value will be rendered.")

    for symbol in ("DXY", "US10Y", "WTI", "GOLD", "SILVER", "VIX", "SPY"):
        entry = result.get(symbol, {})
        append_data_source_log(
            symbol,
            str(entry.get("source", "unavailable")),
            fallback_used=str(entry.get("source", "")).lower() in {"stooq", "cache", "stub"},
            stale_risk=not validate_data_point(entry.get("price"), entry.get("timestamp")),
        )
    append_confidence_score_log(int(meta["confidence_score"]))

    save_market_data_cache(_cache_preserving_commodities(result), source=outcome.source)
    return result


def _chg_str(val: float | None, is_yield: bool = False, include_5d: bool = False,
             week_chg: float | None = None) -> str:
    """Format a change value for display."""
    if val is None:
        return "N/A"
    if is_yield:
        sign = "+" if val >= 0 else ""
        base = f"{sign}{val:.0f}bps"
    else:
        sign = "+" if val >= 0 else ""
        base = f"{sign}{val:.1f}%"
    if include_5d and week_chg is not None:
        if is_yield:
            s2 = "+" if week_chg >= 0 else ""
            base += f" / {s2}{week_chg:.0f}bps 5D"
        else:
            s2 = "+" if week_chg >= 0 else ""
            base += f" / {s2}{week_chg:.1f}% 5D"
    return base


def build_macro_bar(md: dict) -> list[dict]:
    """Build ordered macro bar items."""
    items = []

    def add(name: str, label: str | None = None, include_5d: bool = False):
        d = md.get(name, {})
        is_yield = d.get("is_yield", False)
        chg = _chg_str(d.get("day_chg"), is_yield, include_5d, d.get("week_chg"))
        est = " ~est" if d.get("estimated") else ""
        badge_text, badge_tone = _source_badge(d)
        items.append({
            "name": label or name,
            "value": d.get("formatted", "N/A"),
            "change": chg,
            "estimated": d.get("estimated", False),
            "direction": "up" if d.get("day_chg") is not None and d.get("day_chg") > 0 else "down" if d.get("day_chg") is not None and d.get("day_chg") < 0 else "flat",
            "badge_text": badge_text,
            "badge_tone": badge_tone,
        })

    add("DXY")
    add("US10Y")
    add("REAL10Y", label="REAL10Y ~est")
    add("WTI")
    add("GOLD")
    add("SILVER")
    add("SPY")
    add("QQQ")
    add("BTC")
    add("VIX")
    return items


# ── Narrative layer ─────────────────────────────────────────────────────────

NARRATIVE_SCHEMA = {
    "system_state": "string (2-4 short paragraphs, Clive-style: clear, direct, references specific data values, no fluff)",
    "system_state_action": "string (short directive line prefixed in UI with an arrow; what to do or expect next)",
    "system_state_action_tone": "positive|negative|neutral",
    "events": {
        "HIGH": "list of {event: str, impact: str}",
        "MEDIUM": "list of {event: str, impact: str}",
        "LOW": "list of {event: str, impact: str}",
    },
    "plumbing": "string (2-4 compact sentences explaining which cross-asset drivers matter most, whether they align or conflict, and what that implies for current market posture)",
    "plumbing_action": "string (short directive line prefixed in UI with an arrow; what to do or expect next)",
    "plumbing_action_tone": "positive|negative|neutral",
    "energy_interpretation": "string (2-3 sentences on WTI/XLE/OXY context and directional bias)",
    "metals_interpretation": "string (2-3 sentences on gold/silver vs dollar and real yields)",
    "silver_inventory": "string (note on COMEX/LBMA trends or fallback if unavailable)",
    "miners": [
        {
            "ticker": "string",
            "name": "string",
            "structure": "string",
            "relative_strength": "string",
            "interpretation": "string",
            "conclusion": "string",
        }
    ],
    "equities_btc": "string (2-4 compact sentences explaining what happened from prior close into premarket/open setup, including futures reversals, headline shocks, commodity or macro reactions when relevant)",
    "overnight_action": "string (short directive line prefixed in UI with an arrow; what to do or expect next)",
    "overnight_action_tone": "positive|negative|neutral",
    "setups": [
        {
            "ticker": "string",
            "bias": "Bullish|Bearish|Neutral",
            "grade": "A|A-",
            "resistance": "string",
            "support": "string",
            "structure": "string (e.g. call spread, put spread, outright)",
            "trigger": "string",
            "invalidation": "string",
            "confidence": "Low|Medium|High",
        }
    ],
    "no_setups": "boolean — true if no A/A- setups exist",
    "risk_map": "list of strings (explicit macro triggers only, e.g. 'DXY > 105')",
    "thesis": "string (one sentence, the core macro conviction for today)",
}


def _stub_narrative(md: dict) -> dict:
    """Minimal stub narrative for offline/testing mode."""
    def p(name: str) -> str:
        d = md.get(name, {})
        return d.get("formatted", "N/A")

    return {
        "system_state": (
            f"Markets opened mixed. DXY {p('DXY')}, yields at {p('US10Y')} nominal with "
            f"real rates estimated near {p('REAL10Y')}. Risk sentiment remains data-dependent.\n\n"
            f"WTI at {p('WTI')} with energy sector divergence from equities. "
            f"Gold {p('GOLD')} and Silver {p('SILVER')} reflecting dollar and rate dynamics.\n\n"
            f"VIX at {p('VIX')} — not elevated, but watch for regime shift catalysts."
        ),
        "system_state_action": "Stay selective until rates and dollar stop pulling in different directions.",
        "system_state_action_tone": "neutral",
        "events": {
            "HIGH": [{"event": "Fed speakers scheduled", "impact": "Tone on rate path could move yields and DXY significantly."}],
            "MEDIUM": [{"event": "Oil inventory data", "impact": "Potential catalyst for WTI direction if surprise vs consensus."}],
            "LOW": [{"event": "Earnings season underway", "impact": "Individual movers may affect sector ETFs."}],
        },
        "plumbing": (
            f"DXY {p('DXY')} and US10Y {p('US10Y')} are the main macro constraints, with real yields near {p('REAL10Y')} "
            f"keeping duration-sensitive risk from expanding cleanly. VIX at {p('VIX')} is not confirming outright stress, "
            f"so the tape reads more conflicted than panicked. Oil at {p('WTI')} adds inflation sensitivity without a full "
            f"risk-off impulse, which argues for selective rather than aggressive posture."
        ),
        "plumbing_action": "Favor selective risk rather than broad beta until the driver stack aligns.",
        "plumbing_action_tone": "neutral",
        "energy_interpretation": f"WTI at {p('WTI')}. XLE and OXY tracking futures with normal beta. No clear dislocation signal.",
        "metals_interpretation": f"Gold {p('GOLD')}, Silver {p('SILVER')}. Real yield {p('REAL10Y')} (est.) — monitor for regime inflection.",
        "silver_inventory": "No new inventory data — structural narrative unchanged.",
        "miners": [
            {
                "ticker": "GDX",
                "name": "VanEck Gold Miners ETF",
                "structure": f"Level at {p('GDX')} — trend direction requires comparison to prior session.",
                "relative_strength": "Compare GDX vs GOLD for miner leverage confirmation.",
                "interpretation": "If GDX underperforms gold, distribution pressure likely.",
                "conclusion": "Monitor GDX/GOLD ratio for accumulation or distribution signal.",
            },
            {
                "ticker": "NEM",
                "name": "Newmont Corporation",
                "structure": f"NEM at {p('NEM')} — large-cap miner with high GOLD beta.",
                "relative_strength": "Should lead GDX in a sustained gold bull move.",
                "interpretation": "Lagging GDX suggests institutional selling or hedging.",
                "conclusion": "Watch NEM relative to GDX for miner sector leadership.",
            },
        ],
        "equities_btc": (
            f"From the prior close into the open setup, index futures remain mixed with SPY {p('SPY')} and QQQ {p('QQQ')} "
            f"not yet breaking into a clean follow-through regime. BTC at {p('BTC')} is still behaving like a loose risk proxy "
            f"rather than a standalone signal, while TSLA {p('TSLA')} and MU {p('MU')} keep single-name beta in focus. "
            f"No major overnight headline shock is confirmed in offline mode, so the open still looks driven primarily by rates, dollar, and commodity tone."
        ),
        "overnight_action": "Expect an open driven by macro confirmation, not overnight momentum alone.",
        "overnight_action_tone": "neutral",
        "setups": [],
        "no_setups": True,
        "risk_map": [
            f"DXY > 105",
            f"REAL10Y > 2.5%",
            f"VIX > 25",
            f"WTI < 65 or WTI > 120",
            f"GOLD < 2800",
        ],
        "thesis": "Range-bound macro regime — preserve capital, wait for conviction entry with clear invalidation.",
    }


def generate_narrative(md: dict) -> dict:
    """Call Claude to generate all narrative sections from live market data."""
    print("Generating narrative via Claude...")

    def fmt(name: str) -> str:
        d = md.get(name, {})
        if d.get("price") is None:
            return f"{name}: N/A"
        chg = d.get("day_chg", 0) or 0
        if d.get("is_yield"):
            sign = "+" if chg >= 0 else ""
            chg_s = f"{sign}{chg:.0f}bps"
        else:
            sign = "+" if chg >= 0 else ""
            chg_s = f"{sign}{chg:.1f}%"
        return f"{name}: {d['formatted']} ({chg_s})"

    data_summary = "\n".join([
        fmt("DXY"), fmt("US10Y"), fmt("REAL10Y"),
        fmt("WTI"), fmt("GOLD"), fmt("SILVER"),
        fmt("SPY"), fmt("QQQ"), fmt("BTC"), fmt("VIX"),
        fmt("XLE"), fmt("OXY"),
        fmt("GDX"), fmt("NEM"), fmt("WPM"),
        fmt("TSLA"), fmt("MU"),
    ])

    today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

    prompt = f"""You are a professional macro trader writing a daily morning report. Today is {today}.

LIVE MARKET DATA:
{data_summary}

NOTE: REAL10Y is estimated as US10Y minus ~2.2% breakeven inflation.

Generate a structured JSON response matching this exact schema:
{json.dumps(NARRATIVE_SCHEMA, indent=2)}

Rules:
- system_state: 2-4 short paragraphs. Reference specific data values. Clive-style: no fluff, direct, intelligent.
- system_state_action: one short directive line on what to do or expect next. Also set system_state_action_tone.
- events: Use current macro context (Fed policy, geopolitical, economic data releases). Be realistic for {today}.
- plumbing: 2-4 compact sentences. Explain which drivers matter most, whether they align or conflict, and what that implies for market posture. This should answer: why is the market behaving this way?
- plumbing_action: one short directive line on what to do or expect next. Also set plumbing_action_tone.
- equities_btc: 2-4 compact sentences. Explain what happened from prior close into the premarket/open setup and why it matters. Include overnight reversals, geopolitical/headline shocks, commodity moves, or macro reactions if relevant. If a meaningful overnight shock exists, fold it into the narrative naturally or flag it briefly as "Headline shock:".
- overnight_action: one short directive line on what to do or expect next. Also set overnight_action_tone.
- miners: Analyze GDX and NEM. Use relative strength vs GOLD price action.
- setups: Only include if genuinely A or A- quality based on current structure. Set no_setups: true if nothing qualifies.
- risk_map: List 3-5 explicit numeric triggers that would invalidate the current thesis.
- thesis: One sentence. Core conviction. No hedging.

Return ONLY valid JSON. No markdown, no code blocks, no commentary."""

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  Warning: ANTHROPIC_API_KEY not set — using stub narrative.")
        print("  To enable AI narrative: export ANTHROPIC_API_KEY=sk-ant-...")
        return _stub_narrative(md)

    client = anthropic.Anthropic(api_key=api_key)
    for attempt in range(1, NARRATIVE_RETRY_ATTEMPTS + 1):
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()
            return json.loads(raw)
        except Exception as exc:
            print(
                f"  Warning: narrative generation attempt {attempt}/{NARRATIVE_RETRY_ATTEMPTS} "
                f"failed ({type(exc).__name__})."
            )

    print("  Warning: narrative generation exhausted retries — using stub narrative.")
    return _stub_narrative(md)


# ── Report assembly ─────────────────────────────────────────────────────────

def build_report_data(md: dict, narrative: dict) -> dict:
    now_vancouver = report_now()
    meta = md.get("_meta", {})
    confidence_score = int(meta.get("confidence_score", compute_data_confidence(md)))
    confidence_text, confidence_tone = _confidence_badge(confidence_score)
    return {
        "timestamp": now_vancouver.strftime("%Y-%m-%d — %H:%M %Z"),
        "generated_line": generated_line(now_vancouver),
        "date": now_vancouver.strftime("%Y-%m-%d"),
        "archive_href": "archive/",
        "confidence_score": confidence_score,
        "confidence_badge_text": confidence_text,
        "confidence_badge_tone": confidence_tone,
        "show_low_confidence_banner": confidence_score < 70,
        "macro_bar": build_macro_bar(md),
        "state_summary": _build_state_summary(md, narrative),
        "financial_plumbing": _build_financial_plumbing(md),
        "system_state": narrative.get("system_state", ""),
        "system_state_action": narrative.get("system_state_action", ""),
        "system_state_action_tone": narrative.get("system_state_action_tone", "neutral"),
        "events": narrative.get("events", {"HIGH": [], "MEDIUM": [], "LOW": []}),
        "plumbing": narrative.get("plumbing", ""),
        "plumbing_action": narrative.get("plumbing_action", ""),
        "plumbing_action_tone": narrative.get("plumbing_action_tone", "neutral"),
        "energy": {
            "wti": md.get("WTI", {}),
            "xle": md.get("XLE", {}),
            "oxy": md.get("OXY", {}),
            "interpretation": narrative.get("energy_interpretation", ""),
        },
        "metals": {
            **_build_metals_context(md),
            "interpretation": narrative.get("metals_interpretation", ""),
        },
        "inventory": narrative.get("silver_inventory", INVENTORY_FALLBACK_TEXT),
        "miners": narrative.get("miners", []),
        "equities": {
            "spy": md.get("SPY", {}),
            "qqq": md.get("QQQ", {}),
            "tsla": md.get("TSLA", {}),
            "mu": md.get("MU", {}),
            "btc": md.get("BTC", {}),
            "context": narrative.get("equities_btc", ""),
            "action": narrative.get("overnight_action", ""),
            "action_tone": narrative.get("overnight_action_tone", "neutral"),
        },
        "setups": narrative.get("setups", []),
        "no_setups": narrative.get("no_setups", True),
        "risk_map": narrative.get("risk_map", []),
        "thesis": narrative.get("thesis", ""),
    }


def get_macro_bundle(*, offline: bool = False) -> dict:
    """Fetch, normalize, and assemble the dashboard-ready macro bundle."""
    market_data = fetch_market_data()
    narrative = _stub_narrative(market_data) if offline else generate_narrative(market_data)
    bundle = build_report_data(market_data, narrative)
    bundle["market_data"] = market_data
    return bundle


# ── Rendering ───────────────────────────────────────────────────────────────

def render_html(report_data: dict, out_path: Path | None = None, *, archive_mode: bool = False) -> Path:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    env.filters["highlight_tickers"] = _highlight_tickers_filter
    template = env.get_template("morning_edge.html")
    render_data = {
        **report_data,
        "design_system_css": shared_design_system_css(page_max="1420px", page_pad_bottom="0"),
    }
    if archive_mode:
        render_data["archive_href"] = "index.html"
    html_content = template.render(**render_data)

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
    print("Morning Macro Edge — Report Generator")
    print("=" * 60)
    failed_stages: list[str] = []

    try:
        market_data = fetch_market_data()
        append_report_log("morning_edge.data_fetch", "success")
    except Exception as exc:
        failed_stages.append("morning_edge.data_fetch")
        append_report_log("morning_edge.data_fetch", "failure", f"exception={type(exc).__name__}: {exc}")
        market_data = build_stub_market_data()

    try:
        narrative = _stub_narrative(market_data) if offline else generate_narrative(market_data)
        report_data = build_report_data(market_data, narrative)
        report_data["market_data"] = market_data
        append_report_log("morning_edge.report_build", "success")
    except Exception as exc:
        failed_stages.append("morning_edge.report_build")
        append_report_log("morning_edge.report_build", "failure", f"exception={type(exc).__name__}: {exc}")
        fallback_market_data = build_stub_market_data()
        report_data = build_report_data(fallback_market_data, _stub_narrative(fallback_market_data))
        report_data["market_data"] = fallback_market_data

    with TemporaryDirectory(prefix="premarket-report-") as tmpdir:
        temp_dir = Path(tmpdir)
        html_temp_path = temp_dir / LIVE_HTML_PATH.name
        pdf_temp_path = temp_dir / LIVE_PDF_PATH.name

        try:
            render_html(report_data, out_path=html_temp_path)
        except Exception as exc:
            print(f"[FAIL] Daily Premarket Report generation failed: {exc}")
            failed_stages.append("morning_edge.html_render")
            append_report_log("morning_edge.html_render", "failure", f"exception={type(exc).__name__}: {exc}")
            report_data["_failed_stages"] = failed_stages
            return report_data
        append_report_log("morning_edge.html_render", "success")
        print(f"[OK] Generated Daily Premarket Report HTML -> {html_temp_path}")

        pdf_generated = False
        if with_pdf:
            try:
                render_pdf(html_temp_path, out_path=pdf_temp_path)
            except Exception as exc:
                print(f"[FAIL] Daily Premarket Report PDF generation failed: {exc}")
                failed_stages.append("morning_edge.pdf_render")
                append_report_log("morning_edge.pdf_render", "failure", f"exception={type(exc).__name__}: {exc}")
            else:
                pdf_generated = True
                append_report_log("morning_edge.pdf_render", "success")
                print(f"[OK] Generated Daily Premarket Report PDF -> {pdf_temp_path}")

        promote_report_artifact(
            report_label="Daily Premarket Report HTML",
            live_path=LIVE_HTML_PATH,
            archive_dir=ARCHIVE_DIR,
            archive_prefix="premarket",
            temp_path=html_temp_path,
            latest_pointer_path=LATEST_HTML_PATH,
        )

        if pdf_generated:
            promote_report_artifact(
                report_label="Daily Premarket Report PDF",
                live_path=LIVE_PDF_PATH,
                archive_dir=ARCHIVE_DIR,
                archive_prefix="premarket",
                temp_path=pdf_temp_path,
                latest_pointer_path=LATEST_PDF_PATH,
            )

    print("=" * 60)
    print(f"Done. Thesis: {report_data['thesis']}")
    report_data["_failed_stages"] = failed_stages
    return report_data


# ── Main ────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Morning Macro Edge report generator")
    parser.add_argument("--offline", action="store_true", help="Skip Claude API, use stub narrative")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF rendering")
    args = parser.parse_args(argv)
    run_report(offline=args.offline, with_pdf=not args.no_pdf)


if __name__ == "__main__":
    main()
