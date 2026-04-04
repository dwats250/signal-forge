#!/usr/bin/env python3
"""Static site builder for Signal Forge report output."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from reports import morning_edge

ROOT_DIR = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT_DIR / "_site"


def _write_index(report_data: dict) -> Path:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    index_path = SITE_DIR / "index.html"
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Signal Forge Reports</title>
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
    width: min(100%, var(--page-max));
    margin: 0 auto;
    padding: 40px 24px 56px;
  }}
  .hero {{
    margin-bottom: 26px;
    padding-bottom: 18px;
    border-bottom: 1px solid var(--border);
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
    font-size: clamp(2rem, 1.7rem + 1vw, 2.8rem);
    line-height: 1.1;
  }}
  .subtitle {{
    max-width: 760px;
    color: var(--text-muted);
    font-size: 1rem;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 18px;
  }}
  .card {{
    display: block;
    text-decoration: none;
    color: inherit;
    background: linear-gradient(180deg, var(--bg-card2), var(--bg-card));
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
  }}
  .card:hover {{
    border-color: rgba(59, 130, 246, 0.45);
  }}
  .card-kicker {{
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--accent-gold);
    margin-bottom: 8px;
  }}
  .card-title {{
    font-size: 1.2rem;
    font-weight: 700;
    margin-bottom: 8px;
  }}
  .card-copy {{
    color: var(--text-muted);
    font-size: 0.96rem;
  }}
  .meta {{
    margin-top: 32px;
    color: var(--text-muted);
    font-size: 0.9rem;
  }}
</style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="eyebrow">Signal Forge</div>
      <h1>Static report dashboard</h1>
      <p class="subtitle">Published HTML entrypoints for the latest Morning Macro Edge report and its dated archive copy.</p>
    </section>
    <section class="grid">
      <a class="card" href="morning_edge.html">
        <div class="card-kicker">Latest report</div>
        <div class="card-title">Morning Macro Edge</div>
        <div class="card-copy">Open the current report build rendered from the shared dashboard template.</div>
      </a>
      <a class="card" href="archive/{report_data['date']}.html">
        <div class="card-kicker">Archive</div>
        <div class="card-title">{report_data['date']}</div>
        <div class="card-copy">Open the dated archive snapshot for the same publish cycle.</div>
      </a>
    </section>
    <div class="meta">Generated {report_data['timestamp']}. Static files live under <code>_site/</code>.</div>
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

    market_data = morning_edge.fetch_market_data()
    if os.environ.get("ANTHROPIC_API_KEY"):
        narrative = morning_edge.generate_narrative(market_data)
    else:
        print("ANTHROPIC_API_KEY not set — using stub narrative.")
        narrative = morning_edge._stub_narrative(market_data)

    report_data = morning_edge.build_report_data(market_data, narrative)
    html_path = morning_edge.render_html(report_data)

    archive_src = morning_edge.ARCHIVE_DIR / f"{report_data['date']}.html"
    site_archive_dir = SITE_DIR / "archive"
    site_archive_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(html_path, SITE_DIR / "morning_edge.html")
    shutil.copy2(archive_src, site_archive_dir / archive_src.name)
    _write_index(report_data)

    print(f"Site index: {SITE_DIR / 'index.html'}")
    print(f"Latest report: {SITE_DIR / 'morning_edge.html'}")
    print(f"Archive copy: {site_archive_dir / archive_src.name}")
    return SITE_DIR


def main() -> None:
    build_site()


if __name__ == "__main__":
    main()
