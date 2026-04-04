#!/usr/bin/env python3
"""Morning Macro Edge — daily one-page macro + execution report."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic
import yfinance as yf
from jinja2 import Environment, FileSystemLoader

# ── Paths ──────────────────────────────────────────────────────────────────

REPORTS_DIR = Path(__file__).parent
TEMPLATE_DIR = REPORTS_DIR / "templates"
OUTPUT_DIR = REPORTS_DIR / "output"
ARCHIVE_DIR = REPORTS_DIR / "archive"

# ── Ticker map ─────────────────────────────────────────────────────────────

TICKERS: dict[str, str] = {
    "DXY": "DX-Y.NYB",
    "US10Y": "^TNX",
    "WTI": "CL=F",
    "GOLD": "GC=F",
    "SILVER": "SI=F",
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


# ── Data layer ─────────────────────────────────────────────────────────────

def build_stub_market_data() -> dict:
    """Deterministic fallback market snapshot for offline/static builds."""
    stub = {
        "DXY": {"price": 104.82, "day_chg": 0.3, "week_chg": 0.9, "formatted": "104.82", "is_yield": False},
        "US10Y": {"price": 4.21, "day_chg": 4.0, "week_chg": 11.0, "formatted": "4.21%", "is_yield": True},
        "WTI": {"price": 81.44, "day_chg": 1.1, "week_chg": 2.7, "formatted": "$81.44", "is_yield": False},
        "GOLD": {"price": 2318.20, "day_chg": 0.4, "week_chg": 1.8, "formatted": "$2318.20", "is_yield": False},
        "SILVER": {"price": 26.11, "day_chg": 0.6, "week_chg": 2.2, "formatted": "$26.11", "is_yield": False},
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

def _format_price(value: float, ticker: str) -> str:
    if ticker in ("GOLD", "SILVER", "WTI", "OXY", "GDX", "NEM", "WPM", "TSLA", "MU"):
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

    all_symbols = list(TICKERS.values())
    try:
        raw = yf.download(
            tickers=all_symbols,
            period="10d",
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
    except Exception as exc:
        print(f"  Warning: live market data fetch failed: {exc}")
        print("  Falling back to deterministic stub market data for this build.")
        return build_stub_market_data()

    try:
        closes = raw["Close"]
        if closes.dropna(how="all").empty:
            print("  Warning: live market data returned no usable close data.")
            print("  Falling back to deterministic stub market data for this build.")
            return build_stub_market_data()
    except Exception as exc:
        print(f"  Warning: malformed market data response: {exc}")
        print("  Falling back to deterministic stub market data for this build.")
        return build_stub_market_data()

    result: dict = {}

    for name, symbol in TICKERS.items():
        try:
            closes = raw["Close"][symbol].dropna()

            if len(closes) < 2:
                result[name] = {"price": None, "day_chg": None, "week_chg": None, "formatted": "N/A"}
                continue

            current = float(closes.iloc[-1])
            prev = float(closes.iloc[-2])
            week_ago = float(closes.iloc[-6]) if len(closes) >= 6 else float(closes.iloc[0])

            if name in YIELD_TICKERS:
                # yields: change in basis points
                day_chg = (current - prev) * 100  # bps
                week_chg = (current - week_ago) * 100  # bps
            else:
                day_chg = (current - prev) / prev * 100
                week_chg = (current - week_ago) / week_ago * 100

            result[name] = {
                "price": current,
                "day_chg": round(day_chg, 2),
                "week_chg": round(week_chg, 2),
                "formatted": _format_price(current, name),
                "is_yield": name in YIELD_TICKERS,
            }

        except Exception as e:
            print(f"  Warning: failed to fetch {name} ({symbol}): {e}")
            result[name] = {"price": None, "day_chg": None, "week_chg": None, "formatted": "N/A"}

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
        }
    else:
        result["REAL10Y"] = {"price": None, "day_chg": None, "week_chg": None, "formatted": "N/A", "estimated": True}

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
        items.append({
            "name": label or name,
            "value": d.get("formatted", "N/A"),
            "change": chg,
            "estimated": d.get("estimated", False),
            "positive": (d.get("day_chg") or 0) >= 0,
        })

    add("DXY", include_5d=True)
    add("US10Y", include_5d=True)
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
    "events": {
        "HIGH": "list of {event: str, impact: str}",
        "MEDIUM": "list of {event: str, impact: str}",
        "LOW": "list of {event: str, impact: str}",
    },
    "plumbing": "string (1-2 sentences on gamma positioning, liquidity, forced vs discretionary flows)",
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
    "equities_btc": "string (2-3 sentences: SPY/QQQ context, TSLA/MU if notable, BTC regime)",
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
        "events": {
            "HIGH": [{"event": "Fed speakers scheduled", "impact": "Tone on rate path could move yields and DXY significantly."}],
            "MEDIUM": [{"event": "Oil inventory data", "impact": "Potential catalyst for WTI direction if surprise vs consensus."}],
            "LOW": [{"event": "Earnings season underway", "impact": "Individual movers may affect sector ETFs."}],
        },
        "plumbing": "VIX regime neutral. Gamma positioning unclear without live GEX data. Discretionary flows dominant.",
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
            f"SPY {p('SPY')}, QQQ {p('QQQ')} — equity indices mixed. "
            f"BTC {p('BTC')} trading in risk-on correlation. TSLA {p('TSLA')}, MU {p('MU')} — monitor for sector rotation."
        ),
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
- events: Use current macro context (Fed policy, geopolitical, economic data releases). Be realistic for {today}.
- plumbing: Focus on known gamma levels, VIX regime, liquidity conditions based on the data shown.
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
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


# ── Report assembly ─────────────────────────────────────────────────────────

def build_report_data(md: dict, narrative: dict) -> dict:
    now_et = datetime.now(ZoneInfo("America/New_York"))
    return {
        "timestamp": now_et.strftime("%Y-%m-%d — %H:%M ET"),
        "date": now_et.strftime("%Y-%m-%d"),
        "macro_bar": build_macro_bar(md),
        "system_state": narrative.get("system_state", ""),
        "events": narrative.get("events", {"HIGH": [], "MEDIUM": [], "LOW": []}),
        "plumbing": narrative.get("plumbing", ""),
        "energy": {
            "wti": md.get("WTI", {}),
            "xle": md.get("XLE", {}),
            "oxy": md.get("OXY", {}),
            "interpretation": narrative.get("energy_interpretation", ""),
        },
        "metals": {
            "gold": md.get("GOLD", {}),
            "silver": md.get("SILVER", {}),
            "real10y": md.get("REAL10Y", {}),
            "interpretation": narrative.get("metals_interpretation", ""),
        },
        "inventory": narrative.get("silver_inventory", "No new inventory data — structural narrative unchanged"),
        "miners": narrative.get("miners", []),
        "equities": {
            "spy": md.get("SPY", {}),
            "qqq": md.get("QQQ", {}),
            "tsla": md.get("TSLA", {}),
            "mu": md.get("MU", {}),
            "btc": md.get("BTC", {}),
            "context": narrative.get("equities_btc", ""),
        },
        "setups": narrative.get("setups", []),
        "no_setups": narrative.get("no_setups", True),
        "risk_map": narrative.get("risk_map", []),
        "thesis": narrative.get("thesis", ""),
    }


# ── Rendering ───────────────────────────────────────────────────────────────

def render_html(report_data: dict) -> Path:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    template = env.get_template("morning_edge.html")
    html_content = template.render(**report_data)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "morning_edge.html"
    out_path.write_text(html_content, encoding="utf-8")

    # Archive copy
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = ARCHIVE_DIR / f"{report_data['date']}.html"
    archive_path.write_text(html_content, encoding="utf-8")

    return out_path


def render_pdf(html_path: Path) -> Path:
    import shutil
    from weasyprint import HTML

    pdf_path = OUTPUT_DIR / "morning_edge.pdf"
    HTML(filename=str(html_path)).write_pdf(str(pdf_path))

    # Archive copy
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(str(pdf_path), str(ARCHIVE_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.pdf"))

    return pdf_path


# ── Main ────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Morning Macro Edge report generator")
    parser.add_argument("--offline", action="store_true", help="Skip Claude API, use stub narrative")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF rendering")
    args = parser.parse_args(argv)

    print("=" * 60)
    print("Morning Macro Edge — Report Generator")
    print("=" * 60)

    market_data = fetch_market_data()

    if args.offline:
        narrative = _stub_narrative(market_data)
    else:
        narrative = generate_narrative(market_data)

    report_data = build_report_data(market_data, narrative)

    html_path = render_html(report_data)
    print(f"HTML: {html_path}")

    if not args.no_pdf:
        pdf_path = render_pdf(html_path)
        print(f"PDF:  {pdf_path}")

    print("=" * 60)
    print(f"Done. Thesis: {report_data['thesis']}")


if __name__ == "__main__":
    main()
