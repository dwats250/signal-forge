# Signal Forge – Volume Profile Entry Layer
## Usage Guide

**Version:** 1.0
**Last Updated:** 2026-04-09

---

## What It Does

The Volume Profile Entry Layer is a TradingView overlay that tells you two things at a glance:

1. **Where price is** — inside, above, or below the value area (where most volume traded)
2. **Whether to act** — three signal types mark the moments where that location produces edge

It does not render a full volume profile histogram. It computes the value area from a rolling window of bars and draws clean lines and signals on top of your existing chart.

---

## What You See

### The Value Area Lines

Two horizontal lines define the value area — the price range where roughly 70% of recent volume traded:

- **Red line** = VAH (Value Area High) — top of the range
- **Green line** = VAL (Value Area Low) — bottom of the range
- **Yellow dotted line** = POC (Point of Control) — highest-volume price in the window (off by default)

These lines update on every bar close. They represent the "fair value" zone the market has been negotiating.

---

### The Background Color

The background behind the bars tells you the current state immediately — no reading required:

| Color | Meaning |
|---|---|
| Faint blue | Price is **inside** value — market is in balance |
| Faint green | Price is **above** value — market is accepting higher prices |
| Faint red | Price is **below** value — market is accepting lower prices |

If it's blue, you're in the value area. That's chop territory — wait for one of the edges.

---

### The Signal Markers

Signals appear as small markers at the close of the qualifying bar. There are three types:

| Marker | Signal | What Happened |
|---|---|---|
| Green arrow up | **Breakout Long** | Price broke above VAH and held for N bars |
| Red arrow down | **Breakout Short** | Price broke below VAL and held for N bars |
| Orange X | **Fade Long / Short** | Breakout attempt failed; price returned inside |
| Aqua dot | **LVN Momentum** | Fast expansion through thin air above/below value |

---

### Retest Zones

After a confirmed breakout, a semi-transparent box appears at the breakout level (VAH or VAL). This marks the key zone where price may pull back and offer a second entry. The box disappears after the configured number of bars.

---

## The Three Signals

### Breakout

**What happened:** Price pushed through VAH or VAL, held outside for the required number of consecutive closes, with no wick rejecting back inside and volume expanding on the move.

**What it means:** The market is being offered at new levels and accepting them. The value area is shifting.

**How to use it:**
- Breakout Long → look for continuation above VAH; VAH becomes support
- Breakout Short → look for continuation below VAL; VAL becomes resistance
- The retest zone marks where to look for a second entry if you missed the first

---

### Fade (Failed Breakout)

**What happened:** Price crossed VAH or VAL but immediately returned inside value within 1–2 bars, leaving a clear rejection wick.

**What it means:** The breakout was rejected. Sellers (on a failed breakout above VAH) or buyers (on a failed breakdown below VAL) stepped in and pushed price back into the range. The value area boundary held.

**How to use it:**
- Fade Short → price failed above VAH, now targeting VAL on the short side
- Fade Long → price failed below VAL, now targeting VAH on the long side
- This is a mean-reversion trade — the value area midpoint or the opposite boundary is the target

**Priority:** If a Fade fires at the same bar as a Breakout, the Fade wins. A failed move always overrides a confirmed move on the same bar.

---

### LVN Momentum

**What happened:** Price made a wide-range candle on thin volume outside the value area — the signature of moving through a Low Volume Node (an area where little price history exists, and therefore little resistance).

**What it means:** The path of least resistance is open. Thin volume above/below value means price can travel far quickly.

**How to use it:**
- Direction follows state: above value = long bias, below value = short bias
- These signals favor continuation — add to a position or enter on the signal bar
- Higher-quality when combined with a prior confirmed Breakout signal

**Note:** LVN detection is a proxy (no full profile available in Pine Script). Expect occasional false signals in choppy conditions. Strict Mode filters the weakest ones.

---

## Settings

| Setting | What It Controls |
|---|---|
| **Lookback Period** | How many bars define the value area. Shorter = more reactive. Longer = more stable. Default 75 works for intraday. |
| **Value Area %** | What % of volume defines the range. 70% is standard volume profile convention. |
| **Acceptance Bars** | How many consecutive closes outside value are required before a Breakout fires. 2 is the minimum meaningful confirmation. |
| **Volume Threshold** | How much above average volume needs to be on signal bars. 1.3× filters out low-conviction moves. |
| **EMA Length** | Used for trend alignment scoring. Signals on the correct side of the EMA score higher. |
| **Retest Zone Duration** | How many bars the retest box persists after a breakout. |

### Toggles

| Toggle | Default | When to Change |
|---|---|---|
| **Show Background** | On | Turn off if you find the color distracting — you lose state-at-a-glance |
| **Show Signals** | On | Always on — this is the core output |
| **Show Retest Zones** | On | Turn off on busy charts if boxes add clutter |
| **Show POC** | Off | Turn on to see the highest-volume price in the window |
| **Strict Mode** | Off | Turn on in choppy conditions — only shows signals scoring 2 or higher |
| **Enable LVN** | On | Turn off if you only want breakout/fade signals |

---

## Signal Quality

Every signal is scored 0–3 based on three conditions:

- **+1** — Volume expanded on the signal bar
- **+1** — No rejection wick on the confirming bars
- **+1** — Price is on the correct side of the EMA (trend alignment)

With **Strict Mode off**, all signals appear — including weak ones. Use this when learning the indicator or in trending markets where even lower-quality signals follow through.

With **Strict Mode on**, only signals scoring 2 or 3 appear. Use this in choppier conditions or when you want higher-confidence setups only.

---

## Practical Workflow

**Step 1 — Orient:** Look at the background color. Blue = inside, green = above, red = below. If it's blue, wait.

**Step 2 — Watch the lines:** Is price approaching VAH from below (potential breakout or rejection setup)? Approaching VAL from above?

**Step 3 — Wait for a signal:** Don't anticipate. The signal fires on bar close after conditions are confirmed. A signal with a retest zone already drawn means there's already a second-entry level marked.

**Step 4 — Check the score:** If Strict Mode is off and you see a signal, mentally note whether volume confirmed it (score ≥ 2). Lower-score signals require more context from other indicators.

---

## When Not to Trade the Signals

- **Price is inside value (blue background)** — signals are disabled in this zone by design. Wait for a boundary test.
- **VAH and VAL are very close together** — narrow value areas mean the market is compressing. Either a big expansion is coming or it's noise. Wait for the move.
- **Around major news events** — value area computation is a rolling average. Sudden news gaps will distort the levels temporarily. Skip the first few bars after a spike.
- **Strict Mode off in a choppy session** — if you're seeing a lot of Fade signals firing repeatedly at the same level, the market is grinding, not trending. Switch to Strict Mode or step aside.

---

## Alerts

All five signal types have TradingView alert conditions configured. Set them from the Alerts panel:

- Breakout Long / Breakout Short
- Fade Long / Fade Short
- LVN Momentum

Recommended: enable alerts only for the signal type you're actively trading to avoid noise.

---

## Phase 2 (Coming)

- Higher-timeframe value area (daily VA on intraday charts)
- Retest signal — alert when price re-touches VAH/VAL after a breakout
- Sniper integration — value area state feeds directly into entry scoring
