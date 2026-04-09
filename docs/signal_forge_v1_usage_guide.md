# Signal Forge v1 — Usage Guide

**Indicator:** Signal Forge v1 — 0DTE + Volume Profile
**Chart:** 5-minute | Timezone: Exchange local
**Version:** 1.0
**Last Updated:** 2026-04-09

---

## What It Does

Signal Forge v1 is a qualification and alert engine for 0DTE and intraday setups. It does not paint arrows on every bar. It watches the market continuously and only fires when a specific sequence of conditions aligns:

1. The ticker is in the approved universe
2. The session is tradeable (Open Drive, Midday, or Power Hour)
3. Bias is clear (EMA9/EMA21 + VWAP agreement)
4. Price is near a key level
5. The setup scores ≥ 7 out of 8
6. A trigger fires (breakout, reclaim, or pullback confirmation)

The Volume Profile layer adds value area context (VAH/VAL) and three additional signal types on top of the core system.

---

## Approved Ticker Universe

The indicator only qualifies setups on these tickers:

| Tier | Tickers | Notes |
|---|---|---|
| Tier 1 | SPY, QQQ | Core — always valid |
| Tier 2 | NVDA, TSLA, AMD, SMCI, META | Require macro alignment (vs. SPY/QQQ) |
| Optional | MSTR, COIN | Treated as Tier 1 for macro |

On any other ticker, a warning label appears and no signals fire.

---

## Sessions

The indicator recognizes six time windows (exchange timezone):

| Session | Time | Tradeable |
|---|---|---|
| Premarket | 04:00–09:29 | No |
| Open Drive | 09:30–10:29 | Yes |
| Midday | 10:30–14:29 | Yes (pullback/reclaim only) |
| Late Day | 14:30–14:59 | No |
| Power Hour | 15:00–16:00 | Yes |
| Postmarket | 16:01–20:00 | No |

Background colors show the current session when enabled. **If two sessions overlap (session conflict), all signals are blocked.**

The three valid sessions accept different trigger types:
- **Open Drive** — breakout only, requires 1.75× volume
- **Midday** — retest and reclaim only (no raw breakouts)
- **Power Hour** — all trigger types

---

## What You See

### Key Level Lines

Four types of horizontal levels, drawn at the last bar:

| Line | Style | Color | Meaning |
|---|---|---|---|
| Opening Range High/Low | Dashed | Yellow | 09:30–09:45 range |
| Premarket High/Low | Dotted | Purple | 04:00–09:29 range |
| Previous Day High/Low | Dotted | Gray | Prior session H/L |
| VWAP | — | (via EMA plots) | Volume-weighted average price |

These are the **active levels** the system uses for key level detection. A setup only qualifies when price is within 0.3% of a level in its bias direction.

### EMAs

- **EMA 9** — blue line, fast trend
- **EMA 21** — orange line, slow trend

Bias is determined by:
- **Bullish**: EMA9 > EMA21 AND close > VWAP
- **Bearish**: EMA9 < EMA21 AND close < VWAP
- **Mixed**: anything else — no setup qualifies

### Session Backgrounds

Faint background colors mark the current session (when Show Session Background is on):

| Color | Session |
|---|---|
| Faint green | Open Drive |
| Faint blue | Power Hour |
| Faint red | Midday |
| Faint orange | Late Day |
| Faint purple | Premarket |

### State Dots (bottom of chart)

Two small circles plot below every bar:

- **Blue dot** — state is READY (all conditions met, waiting for trigger)
- **Orange dot** — state is ALERT (trigger fired, setup is live)

### Alert Label

When a setup fires, a large colored label appears above/below the bar:

```
▲ 7/8
bullish
```

Green label = bullish alert. Red label = bearish alert. The number is the score.

### Value Area Lines (VP Layer)

- **Red line** — VAH (Value Area High)
- **Green line** — VAL (Value Area Low)
- **Yellow dotted line** — POC (off by default)

These update on every bar close from a rolling 75-bar volume-weighted window.

### VP Signal Markers

| Marker | Color | Meaning |
|---|---|---|
| Arrow up | Lime | VP Breakout Long — accepted above VAH |
| Arrow down | Red | VP Breakout Short — accepted below VAL |
| X cross | Orange | VP Fade — failed breakout/breakdown |
| Dot | Aqua | VP LVN Momentum — fast expansion |

### VP Retest Zones

After a confirmed VP Breakout, a semi-transparent box appears at the breakout level (VAH or VAL ±0.25× ATR). It marks the retest zone and disappears after 10 bars by default.

---

## The State Machine

The indicator runs a four-state machine. Signals only fire at specific transitions.

```
SCAN → READY → ALERT → INVALID → SCAN
```

### SCAN
Default state. The system is watching. No conditions are met yet. Nothing is plotted.

### READY
All qualification conditions are met:
- Score ≥ 6
- Clear bias (bullish or bearish)
- Tier 2 macro aligned
- Not hard-extended from VWAP
- No EMA21 block
- Not choppy
- At a key level
- In a valid session

**Blue dots appear.** The system is waiting for a trigger.

### ALERT
A trigger fired while in READY state with score ≥ threshold (default 7):
- **Open Drive**: breakout above/below active level with 1.75× volume
- **Midday**: retest hold or reclaim confirmation
- **Power Hour**: any trigger type

**Orange dots appear. Alert label fires. One `alert()` call emits the full payload.** The alert fires once per setup lifecycle — not on every bar.

### INVALID
The setup broke down:
- Session ended or conflicted
- Price became choppy
- Price extended hard from VWAP or EMA21
- Price broke the invalidation reference level (active level ±0.1%)
- Locked structure broke (price crossed EMA21 against bias)

The system resets to SCAN once price moves >0.5% away from the locked level.

---

## The Scoring Model (0–8)

Scored only when no hard disqualifier is present.

| Condition | Points |
|---|---|
| Macro alignment (same bias as SPY/QQQ) | +2 |
| Structure alignment (EMA9 vs EMA21, not choppy) | +2 |
| Volume expansion (≥1.5× 60-min average) | +2 |
| Not hard-extended from VWAP (<1.5%) | +1 |
| At a key level (within 0.3%) | +1 |

**Penalties (subtracted from score):**

| Condition | Penalty |
|---|---|
| EMA9 distance > 0.8% | −1 |
| ATR exhaustion (bar range > 0.8× ATR) | −1 |
| Too many push legs (≥2 in lookback) | −1 |
| 3+ push legs | Hard block (no alert regardless of score) |

**Perfect score = 8.** Default alert threshold = 7. Lower to 6 in slower sessions.

---

## Hard Disqualifiers

If any of these are true, the score is forced to 0 and no setup qualifies:

- Ticker not in approved universe
- Price hard-extended from VWAP (>1.5%)
- Price too far from EMA21 (>1.5%)
- No key levels exist (no OR, PM, or PDH/PDL data)
- Volume < 50% of average (low liquidity)
- ATR below minimum threshold (default 0.30)
- Not intraday timeframe
- Tier 2 macro misaligned
- No clear bias (mixed EMA/VWAP)
- Session conflict
- VP bias incompatible (only when Gate Alerts by VP State is enabled)

---

## The Alert Payload

When a setup fires, the `alert()` call sends a structured message:

```
ALERT | SPY | bullish | BREAKOUT
Score: 7/8
Raw Score: 8
Session: OPEN
Level: 523.45
Invalidation: 523.19
EMA9 Dist: 0.12%
EMA21 Dist: 0.34%
Legs: 1
Time: 09:47
```

Use this payload in webhook integrations or TradingView alert notifications.

---

## Volume Profile Layer

The VP layer runs independently of the core qualification system. It provides two things:

**1. Value Area Context** — Where is price relative to where most volume traded?

| State | Meaning |
|---|---|
| Inside Value | Market is in balance. Expect chop. Wait for a boundary test. |
| Above Value | Market is accepting higher prices. Bullish context. |
| Below Value | Market is accepting lower prices. Bearish context. |

**2. Three VP Signals** — See the [Volume Profile Usage Guide](volume_profile_usage_guide.md) for full detail on Breakout, Fade, and LVN Momentum.

**Integration with core system:**

By default, VP runs as a visual overlay only — it does not affect Signal Forge alerts. Enable **Gate Alerts by VP State** to use VP as a hard filter:
- Bullish alerts blocked when price is below value
- Bearish alerts blocked when price is above value

This is the highest-conviction configuration: Signal Forge score ≥ 7 AND VP state aligned.

---

## The Debug Table

Bottom-right corner. Visible when Show Debug Labels is on.

| Row | Shows |
|---|---|
| TZ | Exchange timezone |
| Time | Current exchange time (HH:MM) |
| Session | Current session name |
| Conflict | YES if session overlap detected |
| State | SCAN / READY / ALERT / INVALID |
| Score | `7 (8-1)` format — final (raw - penalty) |
| Bias | BULL / BEAR / MIXED |
| Macro | BULL / BEAR (SPY or QQQ proxy) |
| Vol Ratio | Current bar volume vs. 60-min avg |
| EMA Dist | Distance from EMA9 and EMA21 as % |
| Ext Flag | OK / EMA9_PENALTY / EMA21_BLOCK |
| Exhaust | OK / ATR_EXHAUST |
| Legs | Push leg count in lookback window |
| Hard Rej | YES / NO |
| Value Area | ABOVE / INSIDE / BELOW (VP layer) |
| VAH | Rolling value area high |
| VAL | Rolling value area low |

---

## Settings Reference

### Filters

| Setting | Default | Notes |
|---|---|---|
| Min ATR Threshold | 0.30 | Skip setups when volatility is too low |
| Alert Score Threshold | 7 | Lower to 6 for slower sessions |

### Display

| Setting | Default | Notes |
|---|---|---|
| Show Debug Labels | On | Alert labels + state dots + debug table |
| Show Key Level Lines | On | OR, PM, PDH/PDL lines |
| Show Session Background | On | Session color shading |

### Volume Profile

| Setting | Default | Notes |
|---|---|---|
| Lookback Period | 75 bars | Shorter = more reactive VA |
| Value Area % | 70% | Standard volume profile convention |
| Acceptance Bars | 2 | Consecutive closes to confirm VP breakout |
| Volume Threshold | 1.3× | For VP signal volume confirmation |
| EMA Length | 21 | Trend filter for VP signal scoring |
| Retest Zone Duration | 10 bars | How long retest box persists |
| Show Background State | Off | VP state shading (off — session colors active) |
| Show VP Signals | On | Breakout / Fade / LVN markers |
| Show Retest Zones | On | Box at VAH/VAL after VP breakout |
| Show POC Line | Off | Optional POC — approximation only |
| Strict Mode | Off | Only show VP signals scoring ≥ 2 |
| Enable LVN Signal | On | LVN Momentum marker |
| Gate Alerts by VP State | Off | Use VP as hard filter on core alerts |

---

## Practical Workflow

**Before the open:**
- Confirm the ticker is in the approved universe
- Note premarket high/low — these become active levels
- Check yesterday's high/low — key reference for the first breakout

**At 09:30 (Open Drive):**
- Watch for bias to form: EMA9 crosses EMA21, price holds above/below VWAP
- Watch for price to approach a key level (OR high, PM high, PDH)
- Blue dot = READY. The system is aligned. Wait for the breakout candle.
- Orange dot = ALERT fired. Check the score in the debug table. Act or pass.

**During Midday (10:30–14:30):**
- No raw breakouts — only pullback retests and reclaims qualify
- Look for price to pull back to a key level that held during the open drive
- Blue dot at a level with bullish bias = potential midday retest setup

**At 15:00 (Power Hour):**
- All trigger types valid again
- Momentum setups are stronger here — look for confirmation of direction set during open

**Always:**
1. Check the debug table — State, Score, Bias, Macro must all confirm
2. Check VAH/VAL position — are you trading with or against value?
3. Note the invalidation level printed in the alert payload — that's your stop reference

---

## When Not to Trade the Alert

- **State = INVALID on the same bar as the alert** — the setup degraded immediately
- **Score = 6 with threshold at 7** — alert shouldn't have fired, check settings
- **VP state opposes bias** — e.g., bullish alert but price is below VAL (consider enabling Gate Alerts)
- **Late Day (14:30–15:00)** — no valid session, all signals blocked by design
- **Session conflict showing YES** — two session windows overlapping, skip the bar
- **Vol Ratio < 1.0** — volume didn't confirm, lower-conviction even if alert fired

---

## Alerts Setup

Two alert types available:

**1. Signal Forge v1 (core system)**
- Fires once per setup lifecycle
- Use `alert()` payload for full context (score, level, invalidation, session, time)
- Set to: "Once Per Bar Close"

**2. VP Alerts (5 conditions)**
- VP Breakout Long / Short
- VP Fade Long / Short
- VP LVN Momentum
- Independent of core state machine — fire on signal bar close

Recommended: enable Signal Forge v1 alert as your primary. Add VP Breakout alerts as confirmation context when they align with an active setup.

---

## Invalidation Reference

Every alert locks an invalidation level at fire time:
- **Bullish**: active level × 0.999 (0.1% below)
- **Bearish**: active level × 1.001 (0.1% above)

If price closes beyond this level, state transitions to INVALID automatically. Use it as your hard stop reference — not a precise stop price, but the structural level below/above which the setup is dead.
