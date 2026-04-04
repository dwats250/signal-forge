# Macro Morning Edge — Architecture & UX PRD (v1)

## Overview

Macro Morning Edge is a static market intelligence report generator that transforms macro and market data into a structured, daily decision-making interface.

The system is designed to:

- provide fast situational awareness before market open
- surface cause -> effect -> risk -> action
- remain simple, portable, and reliable

## Core Objective

Deliver a 10-second decision interface that answers:

1. What kind of day is it?
2. What is driving the market?
3. What matters most right now?
4. What could disrupt the market?
5. How aggressive should I be?

## System Architecture

### 1. Data Layer

Responsible for:

- fetching market and macro data
- handling failures and fallbacks
- providing normalized inputs

Key behaviors:

- retry missing symbols individually
- fallback to cached data if live fetch fails
- never render silent `NA`
- use explicit placeholders for unavailable sources

### 2. Report Logic Layer (`reports/morning_edge.py`)

Responsible for:

- building structured report sections
- interpreting macro relationships
- generating:
  - One-Line Thesis
  - System State
  - Financial Plumbing
  - Events
  - Watchlists
  - Metals context

This layer defines WHAT the report says.

### 3. Presentation Layer (`reports/templates/morning_edge.html`)

Responsible for:

- layout
- typography
- hierarchy
- visual clarity

This layer defines HOW the report looks.

### 4. Output Layer

Generated artifacts:

- `reports/output/morning_edge.html` -> current report
- `reports/archive/YYYY-MM-DD.html` -> historical snapshots

Purpose:

- daily usability
- long-term auditability

## Page Structure (Finalized Flow)

### Tier 1 — Decision Strip (Above the Fold)

- One-Line Thesis (dominant)
- Compact Macro Strip (condensed tickers + % change)

Goal:
Immediate situational awareness.

### Tier 2 — Explanation Layer

- System State
  - colored cells (green/red/neutral)
- Financial Plumbing
  - compact grid (no large bars)
  - includes:
    - value
    - absolute change
    - % change

Goal:
Explain why the current environment exists.

### Tier 3 — Risk Layer

- High Impact Events
  - equal-width impact columns
  - volatility guidance

Goal:
Identify potential disruptions.

### Tier 4 — Context Layer

- Overnight Context
  - positioned in upper-mid page
  - not buried

Goal:
Provide session continuity.

### Tier 5 — Action Layer

- Top Setups
- Miners Watchlist (formerly Secondary Watchlist)

Requirements:

- clean spacing
- label separation:
  - Structure
  - Relative Strength
  - Interpretation

### Tier 6 — Supporting Layer

- Metals
- Appendix

Goal:
Specialized and reference data.

## UX / Design Principles

### 1. Hierarchy First

- not all sections are equal
- prioritize decision-making speed

### 2. Information Density with Clarity

- compact but readable
- avoid wasted vertical space

### 3. Mobile + Desktop Balance

- mobile = primary experience
- desktop = slightly reduced scale
- no oversized cards on large screens

### 4. No Redundancy

- eliminate duplicate macro summaries
- each section must serve a unique purpose

## Financial Plumbing Design

- use compact grid (not bars)
- equal-sized cells
- each cell shows:
  - ticker
  - value
  - change
  - %
- allow short descriptive text below grid

## System State Design

- colored cells:
  - green = supportive
  - red = adverse
  - neutral = muted
- slightly reduced size vs prior version
- keep explanatory text

## Watchlist Formatting Fix (Required)

Ensure:

- labels do not merge with text
- proper spacing between:
  - Structure
  - Relative Strength
  - Interpretation
- clear visual grouping per item

## Metals Section (Deferred Data Integration)

Current scope:

- Gold
- Silver
- AU/AG ratio
- COMEX reference (existing)

Placeholders required:

- "Shanghai data not yet integrated"
- "Inventory data coming soon"

Constraints:

- no new APIs
- no scraping
- no partial data

Future:

- plug in real sources without UI changes

## Validation Checklist

- [ ] One-Line Thesis visible immediately on load
- [ ] Macro strip readable without scrolling
- [ ] System State visually clear and color-coded
- [ ] Financial Plumbing compact and balanced
- [ ] High Impact Events aligned correctly
- [ ] Overnight Context not buried
- [ ] Watchlist spacing bug resolved
- [ ] Desktop scale reduced appropriately
- [ ] Mobile layout remains clean
- [ ] No `NA` values rendered
- [ ] Deferred placeholders visible for missing metals data

## Constraints

- No redesign
- No feature expansion
- No new data sources (for now)
- Minimal, controlled changes only

## Next Phases (Roadmap)

### Phase 1 — Stabilization (current)

- finalize layout
- ensure reliability
- daily usage

### Phase 2 — Feedback Loop

- observe real usage
- refine hierarchy

### Phase 3 — Data Expansion

- metals inventory
- Shanghai pricing

### Phase 4 — Intelligence Layer

- stronger thesis generation
- cross-asset interpretation

### Phase 5 — Productization

- sharing
- distribution
- potential monetization

## Definition of Success

A user can open the report and within 10 seconds:

- understand market state
- identify key drivers
- recognize main risk
- decide on posture

## One-Line Summary

> Macro Morning Edge is a daily, static, macro-driven decision interface that transforms market data into fast, actionable insight.
