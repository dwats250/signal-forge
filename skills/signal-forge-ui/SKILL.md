---
name: signal-forge-ui
description: Design high-signal, structured UI/UX for Signal Forge dashboards and reports. Focus on layout, hierarchy, and decision clarity.
---

# Signal Forge UI Skill

## Goal
Design interfaces that maximize clarity and decision speed in a trading environment.

## Core Principles

### 1. Hierarchy First
- Most important information must be visible immediately
- No scrolling required to see top signals
- Group related elements tightly

### 2. Decision Speed
User must understand within 5 seconds:
- market state
- top opportunities
- key risks

### 3. Signal Separation
Always visually distinguish:
- Top signals (A tier)
- Secondary setups (B tier)
- Watchlist
- Rejected

### 4. Minimal Noise
- Avoid long text blocks
- Prefer badges, short labels, compact stats
- Remove redundant labels

## Layout Structure

Every page should follow:

1. Market Summary (top)
2. Key Drivers / Events
3. Top Signals (A tier)
4. Secondary Setups (B tier)
5. Watchlist
6. Rejected / Notes

## UI Patterns

### Cards
Use for:
- signals
- setups
- macro summaries

Each card includes:
- ticker
- bias
- score
- key levels
- one-line rationale

### Badges
Use for:
- grade (A+, A, B)
- confidence
- volatility
- liquidity

### Layout Rules

- Use grid (max 2-3 columns)
- Avoid long vertical stacks
- Prioritize above-the-fold content
- Keep spacing tight and consistent

## Output Expectations

When invoked:
1. Provide section layout
2. Define hierarchy clearly
3. Suggest component structure
4. Do NOT focus on styling details
