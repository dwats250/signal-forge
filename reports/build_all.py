#!/usr/bin/env python3
"""Static site builder for Signal Forge report output."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from reports import morning_edge
from reports.report_lifecycle import vancouver_date_str

ROOT_DIR = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT_DIR / "_site"


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
    report_data = morning_edge.run_report(offline=offline, with_pdf=False)
    html_path = morning_edge.LIVE_HTML_PATH

    archive_matches = sorted(morning_edge.ARCHIVE_DIR.glob(f"premarket_{vancouver_date_str()}" + "*.html"))
    archive_src = archive_matches[-1] if archive_matches else None
    site_archive_dir = SITE_DIR / "archive"
    site_archive_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(html_path, SITE_DIR / "index.html")
    shutil.copy2(html_path, SITE_DIR / "morning_edge.html")
    if archive_src is not None:
        shutil.copy2(archive_src, site_archive_dir / archive_src.name)
    _write_archive_index(report_data)

    print(f"Site index: {SITE_DIR / 'index.html'}")
    print(f"Latest report: {SITE_DIR / 'morning_edge.html'}")
    if archive_src is not None:
        print(f"Archive copy: {site_archive_dir / archive_src.name}")
    print(f"Archive index: {site_archive_dir / 'index.html'}")
    return SITE_DIR


def main() -> None:
    build_site()


if __name__ == "__main__":
    main()
