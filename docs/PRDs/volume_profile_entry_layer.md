# PRD: Signal Forge – Volume Profile Entry Layer

**Layer:** Execution (TradingView Pine Script v5)
**Owner:** Dustin Watson
**Version:** 1.2
**Status:** Draft
**Last Updated:** 2026-04-09

---

## Objective

A lightweight overlay indicator that gives traders clear, instant context about where price is relative to value — and fires clean signals at the three most actionable moments.

1. Derive rolling Value Area (VAH / VAL) without rendering a histogram
2. Show at a glance whether price is inside, above, or below value
3. Fire one of three signals: Breakout, Fade, or LVN Momentum
4. Zero clutter — every visual element earns its space

---

## Not In Scope

- Volume profile histogram or TPO chart rendering
- More than 3 signal types
- Automated execution or trade management
- Backtesting or session-based profiles
- Tick-level data (bar-aggregated volume only)

---

## Constraints

- Pine Script v5, standalone overlay indicator
- No histogram rendering, no dense overlays
- Max 1 loop per bar, bounded by lookback
- Must load fast on mobile and intraday timeframes
- Delivered as a separate indicator; merged with existing script only after validation

---

## Inputs

| Input | Default | Purpose |
|---|---|---|
| `Lookback Period` | 75 bars | Window for value area computation |
| `Value Area %` | 70% | Volume % that defines the value area |
| `Acceptance Bars` | 2 | Consecutive closes outside value to confirm breakout |
| `Volume Threshold` | 1.3× | Relative volume required to qualify a signal |
| `EMA Length` | 21 | Trend alignment filter for signal scoring |
| `Retest Zone Duration` | 10 bars | How long the retest box stays visible after a breakout |

Internal constants (not user-facing):
- Wick rejection threshold: 40% of candle range
- LVN range multiplier: 1.8× ATR
- State tolerance band: 0.1% at VAH/VAL boundaries (prevents boundary flicker)

---

## Value Area Computation

Uses a rolling volume-weighted approximation (no tick data required):

1. Over the lookback window, find the bar with the highest volume — this is the **POC proxy**
2. Expand outward from POC, accumulating volume until `Value Area %` of total window volume is captured
3. The resulting price range is **VAL** (lower bound) and **VAH** (upper bound)

Levels are computed once per bar and held static until the next close.

---

## State

Price location is classified on every bar close:

- **Inside Value** — close between VAL and VAH
- **Above Value** — close above VAH (plus tolerance)
- **Below Value** — close below VAL (minus tolerance)

State changes are the trigger for all signals. Chop inside value produces nothing.

---

## Signals

### 1. Breakout

Price escapes value and holds outside for `Acceptance Bars` consecutive closes with no rejection wick and volume expansion.

- **Breakout Long** — accepted above VAH
- **Breakout Short** — accepted below VAL

Signal fires on the final acceptance bar.

---

### 2. Fade (Failed Breakout)

Price breaks out but immediately returns inside value within 1–2 bars, with a clear rejection wick (≥40% of the candle's range).

- **Fade Long** — failed breakdown; long back toward VAH from VAL
- **Fade Short** — failed breakout; short back toward VAL from VAH

Signal fires on the bar that closes back inside value. If a Fade fires on the same bar as a Breakout, **Fade wins** — the breakout is suppressed.

---

### 3. LVN Momentum

A fast expansion move through a low-resistance zone — approximated by a wide candle on thin volume, away from value boundaries.

All conditions must be true:
- Candle range > 1.8× ATR
- Bar volume < 85% of average
- Close is not within 0.5× ATR of VAH or VAL
- Price is already above or below value (trending context only)

- **LVN Momentum** — directional; long if above value, short if below

Can be disabled via settings.

---

## Signal Scoring

Each signal is scored 0–3 at the time it fires:

| Condition | Points |
|---|---|
| Volume expansion on signal bar | +1 |
| Clean close (no rejection wick) | +1 |
| Price on correct side of EMA | +1 |

**Strict Mode** (optional): Only signals scoring ≥ 2 are shown. Weak signals are silently dropped.

---

## Visualization

### Value Area Lines

- **VAH** — red horizontal line, extends right
- **VAL** — green horizontal line, extends right
- **POC** — yellow dotted line, off by default

### Background Shading

Subtle background color communicates state without annotation:

- Inside Value → faint blue
- Above Value → faint green
- Below Value → faint red

### Signal Markers

Plotted at bar close. One marker per signal — no stacking, no size tiers.

| Signal | Marker | Color |
|---|---|---|
| Breakout Long | Arrow up (below bar) | Lime |
| Breakout Short | Arrow down (above bar) | Red |
| Fade Long | X cross (above bar) | Orange |
| Fade Short | X cross (below bar) | Orange |
| LVN Momentum | Dot (direction-side) | Aqua |

### Retest Zone

After a confirmed breakout, a semi-transparent box is drawn at the breakout level (±0.25× ATR). It persists for `Retest Zone Duration` bars, then disappears. At most one active retest zone per direction.

---

## Settings

| Setting | Default | Description |
|---|---|---|
| Show Background | On | State shading behind price |
| Show Signals | On | Signal markers on chart |
| Show Retest Zones | On | Box at VAH/VAL after breakout |
| Show POC | Off | Optional POC line |
| Strict Mode | Off | Only show signals scoring ≥ 2 |
| Enable LVN | On | Toggle LVN Momentum signal |

---

## Alerts

TradingView alert conditions defined for all 5 signal outputs:

- Breakout Long / Breakout Short
- Fade Long / Fade Short
- LVN Momentum

---

## Integration

**Now:** Standalone overlay. No dependencies.

**Phase 2:**
- Expose signal score and state as plot values for Sniper to consume
- Feed score into Pre-Market ranking
- Accept Macro Pulse bias as trend alignment input

---

## Performance

- All lookback arrays are bounded; no unbounded growth
- VAH/VAL/POC computed once per bar, cached
- No histogram, no per-pixel drawing
- Max 2 active box objects (one retest zone per direction)
- Lines cleared each bar — no accumulation

---

## Validation

| # | Scenario | Expected |
|---|---|---|
| 1 | Breakout above VAH → 2 closes above → no wick → volume up | Breakout Long fires on bar 2 |
| 2 | Price crosses VAH → closes back inside with large upper wick | Fade Short fires; Breakout suppressed |
| 3 | Price chops inside value for 10+ bars | No signals |
| 4 | Wide candle, thin volume, price well above VAH | LVN Momentum fires (long) |
| 5 | Price pokes above VAH intrabar, closes inside | No state change; no signal |
| 6 | Confirmed breakout, price pulls back to VAH | Retest zone visible for duration |
| 7 | Strict Mode on, signal scores 1 | Signal suppressed |
| 8 | LVN conditions met, LVN disabled | No signal |

---

## Open Questions

1. **POC by default?** It's an approximation — show it off by default until validated against real profile data?
2. **Retest signal?** Should re-touching VAH/VAL after a breakout fire its own signal? Not scoped — revisit Phase 2.
3. **Higher-timeframe VA?** Daily value area on a 5-min chart via `request.security()`? Defer to Phase 2.
