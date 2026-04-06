# Visual Design System

Signal Forge pages share one semantic styling layer defined in [reports/design_system.py](/home/dustin/signal-forge/reports/design_system.py).

## Tokens

- Semantic colors:
  `risk-on` / positive = green
  `neutral` / range-bound = gold
  `risk-off` / defensive = red
  `stable` = muted slate
  `emerging` = gold
  `building` = red
  `up` = green
  `down` = red
  `flat` = muted slate
- Spacing:
  `--space-xs`, `--space-sm`, `--space-md`, `--space-lg`, `--space-xl`
- Shared shells:
  `.card`, `.card-emphasis`, `.card-alert`, `.card-bias`, `.card-info`
- Shared pills:
  `.pill` with semantic modifiers such as `.pill-positive`, `.pill-warning`, `.pill-negative`, `.pill-stable`, `.pill-emerging`, `.pill-building`

## Typography

- Page title: strongest hierarchy, bold, minimal accent usage
- Meta/subtitle: smaller muted text
- Section heading: uppercase label treatment via `.card-title`
- Primary value: strong weight, tight line-height
- Supporting text: muted, readable body copy
- Caution text: gold and reserved for implication/risk language

## Emphasis Rules

- Use tone borders/glows only on cards carrying regime, posture, drift, or other core state.
- Bold only primary assets, ticker references, and hard thresholds when that helps scan speed.
- Prefer semantic pills over ad hoc colored labels.
- Avoid hardcoded colors in templates when a shared semantic class already exists.
