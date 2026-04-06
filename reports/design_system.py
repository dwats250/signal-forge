"""Shared visual design system tokens and CSS helpers for report surfaces."""

from __future__ import annotations


def shared_design_system_css(
    *,
    page_max: str = "1200px",
    page_pad_x: str = "24px",
    page_pad_y: str = "22px",
    page_pad_bottom: str = "48px",
    page_gap: str = "18px",
) -> str:
    return f"""
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

  :root {{
    --bg: #0F1218;
    --bg-card: #171B23;
    --bg-card2: #1D2330;
    --border: #2A3140;
    --accent: #5B97E5;
    --accent-gold: #E6B44A;
    --accent-green: #3FD37A;
    --accent-red: #F06B6B;
    --text: #EDF1F7;
    --text-muted: #A8B2C3;
    --text-dim: #7C879A;
    --risk-on: var(--accent-green);
    --risk-neutral: var(--accent-gold);
    --risk-off: var(--accent-red);
    --stable: #A8B2C3;
    --emerging: var(--accent-gold);
    --building: var(--accent-red);
    --dir-up: var(--accent-green);
    --dir-down: var(--accent-red);
    --dir-flat: var(--text-muted);
    --impact-high-bg: #7F1D1D;
    --impact-high-fg: #FCA5A5;
    --impact-medium-bg: #78350F;
    --impact-medium-fg: #FCD34D;
    --impact-low-bg: #14532D;
    --impact-low-fg: #86EFAC;
    --space-xs: 8px;
    --space-sm: 12px;
    --space-md: 16px;
    --space-lg: 20px;
    --space-xl: 24px;
    --page-max: {page_max};
    --page-pad-x: {page_pad_x};
    --page-pad-y: {page_pad_y};
    --page-pad-bottom: {page_pad_bottom};
    --page-gap: {page_gap};
    --card-radius: 12px;
    --pill-radius: 999px;
    --button-radius: 8px;
    --shadow-card:
      0 14px 34px rgba(0, 0, 0, 0.2),
      inset 0 1px 0 rgba(255, 255, 255, 0.03);
    --shadow-positive:
      var(--shadow-card),
      0 0 0 1px rgba(63, 211, 122, 0.08),
      0 0 22px rgba(63, 211, 122, 0.08);
    --shadow-warning:
      var(--shadow-card),
      0 0 0 1px rgba(230, 180, 74, 0.08),
      0 0 22px rgba(230, 180, 74, 0.08);
    --shadow-negative:
      var(--shadow-card),
      0 0 0 1px rgba(240, 107, 107, 0.08),
      0 0 22px rgba(240, 107, 107, 0.08);
  }}

  html, body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    font-size: 15px;
    line-height: 1.62;
    min-height: 100vh;
  }}

  .page {{
    width: min(100%, var(--page-max));
    margin: 0 auto;
    padding: var(--page-pad-y) var(--page-pad-x) var(--page-pad-bottom);
    display: flex;
    flex-direction: column;
    gap: var(--page-gap);
  }}

  .header {{
    display: flex;
    justify-content: space-between;
    gap: var(--space-lg);
    flex-wrap: wrap;
  }}
  .header h1 {{
    font-size: clamp(1.6rem, 1.28rem + 1vw, 2.35rem);
    font-weight: 800;
    letter-spacing: 0.01em;
    color: var(--text);
    line-height: 1.12;
  }}
  .header h1 span {{ color: var(--accent); }}
  .header .ts,
  .header-ts {{
    font-size: 0.84rem;
    color: var(--text-muted);
    letter-spacing: 0.04em;
    line-height: 1.65;
  }}
  .header-week {{
    font-size: 1rem;
    font-weight: 700;
    color: var(--accent-gold);
    margin-top: 4px;
    letter-spacing: 0.02em;
  }}

  .card {{
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.025), rgba(255, 255, 255, 0)),
      var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--card-radius);
    padding: var(--space-lg);
    box-shadow: var(--shadow-card);
  }}
  .card-emphasis {{
    background: linear-gradient(180deg, rgba(91, 151, 229, 0.12), rgba(29, 35, 48, 0.96));
  }}
  .card-alert {{
    border-color: rgba(240, 107, 107, 0.28);
    background: linear-gradient(180deg, rgba(240, 107, 107, 0.08), rgba(29, 35, 48, 0.94));
  }}
  .card-bias {{
    border-color: rgba(230, 180, 74, 0.24);
    background: linear-gradient(180deg, rgba(230, 180, 74, 0.07), rgba(29, 35, 48, 0.92));
  }}
  .card-info {{
    background: linear-gradient(180deg, rgba(91, 151, 229, 0.08), rgba(29, 35, 48, 0.96));
  }}
  .tone-positive {{ border-color: rgba(63, 211, 122, 0.42); box-shadow: var(--shadow-positive); }}
  .tone-warning {{ border-color: rgba(230, 180, 74, 0.42); box-shadow: var(--shadow-warning); }}
  .tone-negative {{ border-color: rgba(240, 107, 107, 0.42); box-shadow: var(--shadow-negative); }}
  .tone-neutral {{ border-color: var(--border); }}

  .card-title {{
    font-size: 0.74rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: var(--space-md);
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .card-title::after {{
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
  }}

  .label-caps {{
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-muted);
  }}
  .value-primary {{
    font-size: clamp(1rem, 0.94rem + 0.42vw, 1.18rem);
    font-weight: 750;
    letter-spacing: 0.01em;
    line-height: 1.35;
    color: var(--text);
  }}
  .text-support {{
    font-size: 0.9rem;
    color: var(--text-muted);
    line-height: 1.6;
  }}
  .text-caution {{
    color: var(--accent-gold);
    font-weight: 600;
  }}
  .asset-strong,
  .threshold {{
    font-weight: 800;
    color: #F7FAFF;
  }}
  .ticker-inline {{
    color: var(--accent);
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }}

  .pill {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 3px 9px;
    border-radius: var(--pill-radius);
    border: 1px solid transparent;
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    line-height: 1.1;
    white-space: nowrap;
  }}
  .pill-positive {{ background: rgba(63, 211, 122, 0.12); border-color: rgba(63, 211, 122, 0.26); color: var(--risk-on); }}
  .pill-warning {{ background: rgba(230, 180, 74, 0.12); border-color: rgba(230, 180, 74, 0.26); color: var(--risk-neutral); }}
  .pill-negative {{ background: rgba(240, 107, 107, 0.12); border-color: rgba(240, 107, 107, 0.26); color: var(--risk-off); }}
  .pill-neutral {{ background: rgba(168, 178, 195, 0.08); border-color: rgba(168, 178, 195, 0.2); color: var(--text-muted); }}
  .pill-stable {{ background: rgba(168, 178, 195, 0.08); border-color: rgba(168, 178, 195, 0.2); color: var(--stable); }}
  .pill-emerging {{ background: rgba(230, 180, 74, 0.12); border-color: rgba(230, 180, 74, 0.26); color: var(--emerging); }}
  .pill-building {{ background: rgba(240, 107, 107, 0.12); border-color: rgba(240, 107, 107, 0.26); color: var(--building); }}
  .impact-HIGH {{ background: var(--impact-high-bg); color: var(--impact-high-fg); }}
  .impact-MEDIUM {{ background: var(--impact-medium-bg); color: var(--impact-medium-fg); }}
  .impact-LOW {{ background: var(--impact-low-bg); color: var(--impact-low-fg); }}
  .conf-HIGH {{ background: rgba(63, 211, 122, 0.12); border-color: rgba(63, 211, 122, 0.26); color: var(--risk-on); }}
  .conf-MEDIUM {{ background: rgba(230, 180, 74, 0.12); border-color: rgba(230, 180, 74, 0.26); color: var(--risk-neutral); }}
  .conf-LOW {{ background: rgba(168, 178, 195, 0.08); border-color: rgba(168, 178, 195, 0.2); color: var(--stable); }}
  .bias-Bullish {{ background: rgba(63, 211, 122, 0.12); border-color: rgba(63, 211, 122, 0.26); color: var(--risk-on); }}
  .bias-Bearish {{ background: rgba(240, 107, 107, 0.12); border-color: rgba(240, 107, 107, 0.26); color: var(--risk-off); }}
  .bias-Neutral {{ background: rgba(168, 178, 195, 0.08); border-color: rgba(168, 178, 195, 0.2); color: var(--stable); }}

  .dir-up,
  .delta-up {{ color: var(--dir-up); }}
  .dir-down,
  .delta-down {{ color: var(--dir-down); }}
  .dir-flat,
  .delta-flat {{ color: var(--dir-flat); }}

  .report-card {{
    background: linear-gradient(180deg, rgba(91, 151, 229, 0.08), rgba(29, 35, 48, 0.96));
    border: 1px solid rgba(91, 151, 229, 0.2);
  }}
  .report-label {{
    font-size: 1.14rem;
    font-weight: 700;
    color: var(--text);
    margin-bottom: var(--space-xs);
  }}
  .report-copy {{
    color: var(--text-muted);
    font-size: 0.96rem;
    line-height: 1.62;
    margin-bottom: 14px;
  }}
  .report-meta {{
    font-size: 0.8rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--accent-gold);
    margin-bottom: 14px;
  }}
  .report-actions {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }}
  .report-link,
  .action-link {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 112px;
    padding: 10px 14px;
    border-radius: var(--button-radius);
    text-decoration: none;
    font-size: 0.9rem;
    font-weight: 700;
    transition: transform 120ms ease, border-color 120ms ease, background 120ms ease, color 120ms ease;
  }}
  .report-link.primary,
  .action-link.primary {{
    color: #08101C;
    background: var(--accent);
    border: 1px solid var(--accent);
  }}
  .report-link.secondary,
  .action-link.secondary {{
    color: var(--text);
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid var(--border);
  }}
  .report-link.ghost,
  .action-link.ghost {{
    color: var(--text-muted);
    background: transparent;
    border: 1px dashed rgba(168, 178, 195, 0.24);
  }}
  .report-link:hover,
  .action-link:hover {{ transform: translateY(-1px); }}
  .report-link.secondary:hover,
  .action-link.secondary:hover {{
    border-color: rgba(91, 151, 229, 0.45);
    color: var(--accent);
  }}

  @media (max-width: 760px) {{
    :root {{
      --page-pad-x: 16px;
      --page-pad-y: 16px;
      --page-pad-bottom: 24px;
      --page-gap: 14px;
    }}
    .card {{ padding: var(--space-md); }}
    .report-link,
    .action-link {{ min-width: 0; }}
  }}
"""
