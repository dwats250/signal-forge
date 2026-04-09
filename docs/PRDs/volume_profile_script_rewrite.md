# PRD: Signal Forge v1 — Volume Profile Integration

**File:** `signal_forge_v1.pine`
**Pine Script Version:** v6
**Owner:** Dustin Watson
**Version:** 1.1
**Status:** Implemented
**Last Updated:** 2026-04-09
**References:**
- Product spec: `docs/PRDs/volume_profile_entry_layer.md`
- Usage guide: `docs/volume_profile_usage_guide.md`
- Archive (wrong target): `pinescripts/archive/0dte_momentum_setup_vp_draft.pine`

---

## Goal

Integrate the Volume Profile Entry Layer into `signal_forge_v1.pine` as new sections alongside the existing 23-section architecture. All existing logic — ticker validation, session engine, opening range, scoring model (0–8), state machine (SCAN/READY/ALERT/INVALID), and alert emission — is preserved unchanged. VP context is additive.

---

## What Stays

All existing functionality is preserved unchanged:

- Ticker validation (approved universe: SPY, QQQ, NVDA, TSLA, AMD, SMCI, META, MSTR, COIN)
- Session logic (premarket, open drive, midday, late day, power hour)
- Opening range (09:30–09:45), premarket high/low, previous day high/low
- VWAP + EMA9/EMA21, macro proxy (SPY↔QQQ cross-reference)
- Volume analysis, extension/exhaustion flags, chop detection
- Bias determination, key level detection, tier 2 alignment gate
- Hard disqualifiers, scoring model (0–8)
- Trigger logic (breakout / reclaim / pullback)
- State machine: SCAN → READY → ALERT → INVALID
- Alert emission (one per lifecycle, rich payload)
- Visual layer (key level lines, session backgrounds, alert labels, state dots)
- Debug table (bottom-right, 15 rows → extended to 18)
- Existing `alertcondition` for Signal Forge v1

---

## What Changes

- **Indicator name** — updated to `"Signal Forge v1 — 0DTE + Volume Profile"`
- **Header** — `max_boxes_count=10` added to `indicator()` call
- **4 new sections** (11b–11e) inserted after Section 11 (ATR Filter): Value Area Computation, VP State Engine, VP Signal Engine, VP Signal Scoring
- **`hard_reject`** — `vp_bias_ok` appended (opt-in via `vp_filter_entries`, default off)
- **Section 22b** added — VP visual layer: VAH/VAL/POC lines, background, signal markers, retest zones
- **Debug table** — extended from 15 to 18 rows; VP rows 15–17: Value Area state, VAH, VAL
- **5 new `alertcondition` calls** — VP Breakout Long/Short, Fade Long/Short, LVN Momentum
- **VP background defaults OFF** — session backgrounds already occupy bgcolor layers

---

## Not In Scope

- Removing or modifying existing BB Squeeze, TICK, or ATR logic
- Full volume profile histogram
- More than 3 VP signal types
- Session-based or tick-level profiles
- Backtesting harness

---

## Section Order (Rewritten Script)

```
1.  INPUTS — existing groups + new "Volume Profile" group
2.  BOLLINGER BAND SQUEEZE — unchanged
3.  NYSE TICK — unchanged
4.  ATR TRAILING STOP — unchanged
5.  VALUE AREA COMPUTATION — new
6.  VP STATE ENGINE — new
7.  VP SIGNAL ENGINE — new
8.  VP SIGNAL SCORING — new
9.  ENTRY SIGNALS — existing logic + optional VP filter
10. EXIT SIGNAL — unchanged
11. PLOTS — existing + new VP visuals appended
12. STATUS TABLE — existing rows + 3 new VP rows
13. ALERTS — existing + new VP alert conditions
```

---

## New Inputs

Add a new input group after the existing `"Display"` group:

**Group: `"Volume Profile"`**

| Input | Type | Default | Description |
|---|---|---|---|
| `vp_lookback` | int | 75 | Lookback window for value area computation |
| `vp_va_pct` | float | 70.0 | % of volume defining the value area |
| `vp_accept_bars` | int | 2 | Consecutive closes outside value to confirm breakout |
| `vp_vol_thresh` | float | 1.3 | Relative volume multiplier for signal qualification |
| `vp_ema_len` | int | 21 | EMA length for trend alignment scoring |
| `vp_retest_bars` | int | 10 | Bars the retest zone persists after a breakout |
| `vp_show_bg` | bool | true | Background state shading |
| `vp_show_signals` | bool | true | VP signal markers |
| `vp_show_retest` | bool | true | Retest zones after breakouts |
| `vp_show_poc` | bool | false | POC line (optional) |
| `vp_strict` | bool | false | Strict mode — only show signals scoring ≥ 2 |
| `vp_enable_lvn` | bool | true | LVN Momentum signal |
| `vp_filter_entries` | bool | false | Use VP state to filter 0DTE entries (opt-in) |

`vp_filter_entries` is the integration gate — off by default so existing behavior is unchanged unless the user enables it.

---

## Section 5 — VALUE AREA COMPUTATION

**Algorithm:**

1. Circular buffer of last `vp_lookback` bars using `array.new_float` for HLC3 and volume
2. Find index of max volume → POC bar
3. Expand outward from POC accumulating volume until `vp_va_pct`% of total window volume is captured
4. Resulting range: `vp_val` (low bound), `vp_vah` (high bound), `vp_poc` (max volume price)

**Rules:**
- All arrays declared with `var`, sized to `vp_lookback`
- Circular buffer: `array.set(arr, bar_index % vp_lookback, value)`
- Results cached in `var float vp_vah`, `var float vp_val`, `var float vp_poc`
- Tolerance band: `vp_tol = close * 0.001` (0.1% of price — prevents boundary flicker)

---

## Section 6 — VP STATE ENGINE

```pine
var int vp_state      = 0    // 0=inside, 1=above, 2=below
var int vp_prev_state = 0

vp_prev_state := vp_state[1]
vp_state      := close > vp_vah + vp_tol ? 1 :
                 close < vp_val - vp_tol ? 2 : 0

vp_above  = vp_state == 1
vp_below  = vp_state == 2
vp_inside = vp_state == 0
```

---

## Section 7 — VP SIGNAL ENGINE

### Acceptance Counters

```pine
var int vp_acc_long  = 0
var int vp_acc_short = 0

vp_acc_long  := vp_above ? vp_acc_long  + 1 : 0
vp_acc_short := vp_below ? vp_acc_short + 1 : 0
```

### Shared Computations

```pine
vp_atr        = ta.atr(vp_lookback)
vp_avg_vol    = ta.sma(volume, vp_lookback)
vp_vol_expand = volume >= vp_avg_vol * vp_vol_thresh

vp_wick_up    = (high - close) / (high - low + 0.0001)
vp_wick_dn    = (close - low)  / (high - low + 0.0001)
vp_clean_long  = vp_wick_up < 0.40
vp_clean_short = vp_wick_dn < 0.40
```

### Breakout Signals

```pine
signal_vp_brk_long  = vp_acc_long  == vp_accept_bars and vp_clean_long  and vp_vol_expand
signal_vp_brk_short = vp_acc_short == vp_accept_bars and vp_clean_short and vp_vol_expand
```

### Fade Signals

```pine
signal_vp_fade_long  = vp_inside and vp_prev_state == 2 and vp_wick_dn >= 0.40
signal_vp_fade_short = vp_inside and vp_prev_state == 1 and vp_wick_up >= 0.40
```

Fade supersedes Breakout on same bar — applied at render time.

### LVN Signal

```pine
vp_near_va   = math.abs(close - vp_vah) < 0.5 * vp_atr or
               math.abs(close - vp_val) < 0.5 * vp_atr

signal_vp_lvn = vp_enable_lvn and not vp_inside and
                (high - low) > vp_atr * 1.8 and
                volume < vp_avg_vol * 0.85 and
                not vp_near_va
```

---

## Section 8 — VP SIGNAL SCORING

```pine
vp_score_vol   = vp_vol_expand ? 1 : 0
vp_score_clean = (signal_vp_brk_long and vp_clean_long) or
                 (signal_vp_brk_short and vp_clean_short) ? 1 : 0
vp_score_trend = (vp_above and close > ta.ema(close, vp_ema_len)) or
                 (vp_below and close < ta.ema(close, vp_ema_len)) ? 1 : 0

vp_score  = vp_score_vol + vp_score_clean + vp_score_trend
vp_gate   = not vp_strict or vp_score >= 2
```

---

## Section 9 — ENTRY SIGNALS (Modified)

Existing logic with optional VP filter:

```pine
vp_long_ok  = not vp_filter_entries or (vp_above or vp_inside)
vp_short_ok = not vp_filter_entries or (vp_below or vp_inside)

long_entry  = sq_ready and tick_bull and ts_flipped_long  and vp_long_ok
short_entry = sq_ready and tick_bear and ts_flipped_short and vp_short_ok
```

When `vp_filter_entries = false` (default): `vp_long_ok` and `vp_short_ok` are both true — zero change to existing behavior.

When `vp_filter_entries = true`: entries are blocked when price is in the opposing value state (e.g., long entry blocked when price is below value).

---

## Section 11 — PLOTS (Additions)

Append after all existing plot calls.

**Color constants (new — add to top of PLOTS section):**

```pine
C_VAH      = color.new(#F44336, 0)
C_VAL      = color.new(#00C853, 0)
C_POC      = color.new(#FFD600, 0)
C_VP_BG_IN = color.new(#2196F3, 92)
C_VP_BG_AB = color.new(#00C853, 92)
C_VP_BG_BL = color.new(#F44336, 92)
C_VP_BRK_L = color.new(#00E676, 0)
C_VP_BRK_S = color.new(#F44336, 0)
C_VP_FADE  = color.new(#FF9800, 0)
C_VP_LVN   = color.new(#00BCD4, 0)
C_VP_RTL   = color.new(#00C853, 85)
C_VP_RTS   = color.new(#F44336, 85)
```

**Value area lines:**

```pine
var line vp_ln_vah = na
var line vp_ln_val = na
var line vp_ln_poc = na

line.delete(vp_ln_vah)
line.delete(vp_ln_val)
line.delete(vp_ln_poc)

vp_ln_vah := line.new(bar_index, vp_vah, bar_index+1, vp_vah, extend=extend.right, color=C_VAH, width=1)
vp_ln_val := line.new(bar_index, vp_val, bar_index+1, vp_val, extend=extend.right, color=C_VAL, width=1)
if vp_show_poc
    vp_ln_poc := line.new(bar_index, vp_poc, bar_index+1, vp_poc, extend=extend.right, color=C_POC, width=1, style=line.style_dotted)
```

**Background:**

```pine
vp_bg = vp_show_bg ? (vp_above ? C_VP_BG_AB : vp_below ? C_VP_BG_BL : C_VP_BG_IN) : na
bgcolor(vp_bg)
```

**Signal markers:**

```pine
vp_no_fade = not signal_vp_fade_long and not signal_vp_fade_short

plotshape(vp_show_signals and signal_vp_brk_long  and vp_gate and vp_no_fade, "VP Breakout Long",  shape.arrowup,   location.belowbar, C_VP_BRK_L, size=size.small)
plotshape(vp_show_signals and signal_vp_brk_short and vp_gate and vp_no_fade, "VP Breakout Short", shape.arrowdown, location.abovebar, C_VP_BRK_S, size=size.small)
plotshape(vp_show_signals and signal_vp_fade_long  and vp_gate,               "VP Fade Long",      shape.xcross,    location.abovebar, C_VP_FADE,  size=size.small)
plotshape(vp_show_signals and signal_vp_fade_short and vp_gate,               "VP Fade Short",     shape.xcross,    location.belowbar, C_VP_FADE,  size=size.small)
plotshape(vp_show_signals and signal_vp_lvn        and vp_gate,               "VP LVN",            shape.circle,    vp_above ? location.belowbar : location.abovebar, C_VP_LVN, size=size.tiny)
```

**Retest zones:**

```pine
var box vp_box_l = na
var box vp_box_s = na
var int vp_box_l_bar = na
var int vp_box_s_bar = na

if signal_vp_brk_long and vp_show_retest
    box.delete(vp_box_l)
    vp_box_l     := box.new(bar_index, vp_vah + 0.25*vp_atr, bar_index + vp_retest_bars, vp_vah - 0.25*vp_atr, bgcolor=C_VP_RTL, border_color=na)
    vp_box_l_bar := bar_index

if signal_vp_brk_short and vp_show_retest
    box.delete(vp_box_s)
    vp_box_s     := box.new(bar_index, vp_val + 0.25*vp_atr, bar_index + vp_retest_bars, vp_val - 0.25*vp_atr, bgcolor=C_VP_RTS, border_color=na)
    vp_box_s_bar := bar_index

if not na(vp_box_l_bar) and bar_index > vp_box_l_bar + vp_retest_bars
    box.delete(vp_box_l)
if not na(vp_box_s_bar) and bar_index > vp_box_s_bar + vp_retest_bars
    box.delete(vp_box_s)
```

---

## Section 12 — STATUS TABLE (Modified)

Extend `table.new` row count from 5 to 8. Add 3 new rows after the existing 5:

| Row | Label | Value | Color Logic |
|---|---|---|---|
| 5 | "VALUE AREA" | "ABOVE" / "INSIDE" / "BELOW" | `C_BULL` / `C_OFF` / `C_BEAR` |
| 6 | "VAH" | price formatted to 2 decimals | `C_HDR` (neutral) |
| 7 | "VAL" | price formatted to 2 decimals | `C_HDR` (neutral) |

Use `str.tostring(vp_vah, "#.##")` for price formatting.

---

## Section 13 — ALERTS (Additions)

Append after existing alert conditions:

```pine
alertcondition(signal_vp_brk_long  and vp_gate, "VP Breakout Long",  "VP: Breakout Long — accepted above VAH")
alertcondition(signal_vp_brk_short and vp_gate, "VP Breakout Short", "VP: Breakout Short — accepted below VAL")
alertcondition(signal_vp_fade_long  and vp_gate, "VP Fade Long",      "VP: Fade Long — failed breakdown, long from VAL")
alertcondition(signal_vp_fade_short and vp_gate, "VP Fade Short",     "VP: Fade Short — failed breakout, short from VAH")
alertcondition(signal_vp_lvn        and vp_gate, "VP LVN Momentum",   "VP: LVN momentum — fast expansion")
```

---

## Indicator Header (Updated)

```pine
//@version=5
indicator("0DTE Momentum Setup + Volume Profile [SMB]", overlay=true,
          max_lines_count=10, max_boxes_count=10,
          max_labels_count=200)
```

`max_labels_count=200` preserved from original. `max_lines_count` and `max_boxes_count` added.

---

## Delivery Criteria

- [ ] All existing 0DTE alerts still present and functional
- [ ] `vp_filter_entries = false` (default) produces identical 0DTE entry signals to the current script
- [ ] VAH/VAL lines visible and updating each bar close
- [ ] Fade suppresses Breakout marker when both fire on same bar
- [ ] Strict Mode hides VP signals scoring < 2
- [ ] Retest boxes expire at `vp_retest_bars` and do not accumulate
- [ ] Status table shows 8 rows with VP state color-coded correctly
- [ ] No Pine Script execution errors on 1m, 5m, 15m timeframes
- [ ] No performance warning (yellow clock) on TradingView standard plan
- [ ] All 8 validation scenarios from the product PRD pass on historical bars
