# Signal Forge V2 — Regime Model

## Overview

The regime engine translates cross-asset price action into one of four market states, then maps that state to an execution posture. It uses a transparent vote-counting model: 8 inputs, each casting ±1 or 0 votes. No weights, no hidden parameters.

**Why transparent?** Because a model you can't audit is a model you can't trust. Every vote is logged in `vote_breakdown` and printed in the terminal report. On any given day you can see exactly why the regime is what it is.

---

## The 8-Input Vote Table

Each input independently casts one vote: `+1` (risk-on), `-1` (risk-off), or `0` (neutral).

| Input | Risk-on (+1) | Risk-off (-1) | Neutral (0) | Logic |
|---|---|---|---|---|
| **SPY** `pct_change` | > +0.3% | < −0.3% | between | Primary equity direction signal |
| **QQQ** `pct_change` | > +0.3% | < −0.3% | between | Tech / risk appetite confirmation |
| **IWM** `pct_change` | > +0.4% | < −0.4% | between | Small-cap risk appetite (higher bar = higher signal quality) |
| **VIX level** | < 18 | > 25 | 18–25 | Fear regime context — 18/25 are standard inflection levels |
| **VIX change** | < −3% | > +5% | between | Rate of change of fear — asymmetric because fear accelerates faster than it recedes |
| **DXY** `pct_change` | < −0.2% | > +0.3% | between | Dollar strength inverts risk; small threshold because DXY moves slowly |
| **TNX** `pct_change` | < −0.5% | > +0.8% | between | Yield direction; asymmetric because a rapid yield spike is more disruptive than gradual decline |
| **BTC** `pct_change` | > +1.5% | < −2.0% | between | Risk appetite proxy; asymmetric because BTC drops harder and faster than it rises |

### Why the Thresholds Are Asymmetric

Risk-off signals travel faster than risk-on signals. VIX spikes in hours; it recedes over days. BTC can drop 5% in an hour and take a week to recover. Asymmetric thresholds reflect this: the system is more easily pushed into risk-off than out of it, which is directionally correct for risk management.

### IWM Has a Higher Bar Than SPY/QQQ

IWM is ±0.4% vs ±0.3% for SPY/QQQ. Small-caps have higher intraday volatility — a 0.3% move in IWM is noise; the same move in SPY is marginal signal. The higher bar makes IWM's vote more meaningful when it does fire.

---

## Confidence Score

```
confidence = abs(net_score) / total_votes
```

- `net_score` = sum of all votes (range: −8 to +8)
- `total_votes` = number of inputs that actually cast a vote (0–8)
- Result: 0.0 to 1.0

**Important edge case:** if an optional symbol (IWM, BTC) is missing, `total_votes` drops to 6. A net score of +4 with 6 votes gives confidence 0.67, vs 0.50 with 8 votes. Missing optional inputs inflate apparent confidence. Check `total_votes` in the audit log if you see unexpectedly high confidence on a thin day.

### Confidence Levels to Remember

| Confidence | Meaning |
|---|---|
| 0.00 | All 8 votes tied or neutral |
| 0.25 | 2/8 lean one way |
| 0.50 | 4/8 agree — minimum floor for any posture |
| 0.63 | 5/8 agree |
| 0.75 | 6/8 agree — AGGRESSIVE_LONG threshold |
| 0.88 | 7/8 agree |
| 1.00 | Unanimous |

---

## Regime Classification Logic

Rules applied in priority order:

```python
# 1. VIX spike overrides everything
if vix_change > +15%:
    return CHAOTIC

# 2. Strong risk-on
if net_score >= 4 and confidence >= 0.60:
    return RISK_ON

# 3. Moderate risk-on
if net_score >= 2:
    return RISK_ON

# 4. Strong risk-off
if net_score <= -4 and confidence >= 0.60:
    return RISK_OFF

# 5. Moderate risk-off
if net_score <= -2:
    return RISK_OFF

# 6. Everything else
return TRANSITION
```

**CHAOTIC always wins.** A VIX spike of +15% in a single session means something has broken. The system stops caring about score and goes straight to STAY_FLAT.

**Why net_score ≥ 2 is enough for RISK_ON (moderate):** At 8 votes, a score of +2 means 5 neutral and 3 positive, or 2 positive and 0 negative with 6 neutral. This is a soft consensus. The system acknowledges the lean without requiring unanimity. In practice, a score of +2 often corresponds to SPY + QQQ both positive — the two primary equity signals — which is a reasonable minimum bar for directional bias.

---

## Posture Mapping

```python
CHAOTIC                             → STAY_FLAT
confidence < 0.50                   → STAY_FLAT
RISK_ON + confidence >= 0.75        → AGGRESSIVE_LONG
RISK_ON + confidence 0.50–0.74      → CONTROLLED_LONG
RISK_OFF + confidence >= 0.55       → DEFENSIVE_SHORT
RISK_OFF + confidence < 0.55        → STAY_FLAT
TRANSITION + VIX > 25              → STAY_FLAT
TRANSITION + VIX <= 25             → NEUTRAL_PREMIUM
```

**STAY_FLAT and CHAOTIC produce zero trade output.** The qualification engine short-circuits at gate 1 for all 16 tradeable symbols. The system commits a NO TRADE report and stops.

---

## Practical Regime Examples

### Example 1: Classic Risk-On Morning

```
SPY +0.8%     → +1  (above +0.3%)
QQQ +1.1%     → +1  (above +0.3%)
IWM +0.6%     → +1  (above +0.4%)
VIX 15.20     → +1  (below 18)
VIX -3.5%     → +1  (below -3%)
DXY -0.4%     → +1  (below -0.2%)
TNX -0.7%     → +1  (below -0.5%)
BTC +2.1%     → +1  (above +1.5%)

net_score = +8  confidence = 1.00  → RISK_ON  → AGGRESSIVE_LONG
```

### Example 2: Friday Chop (Today's Reading)

```
SPY +0.03%    → 0
QQQ +0.27%    → 0
IWM +0.01%    → 0
VIX 19.23     → 0  (in 18–25 neutral zone)
VIX -1.28%    → 0  (between -3% and +5%)
DXY -0.17%    → 0  (between -0.2% and +0.3%)
TNX +0.56%    → 0  (between -0.5% and +0.8%)
BTC +1.67%    → +1 (above +1.5%)

net_score = +1  confidence = 0.125  → TRANSITION  → STAY_FLAT
```

BTC votes positive, but one vote is not a regime. Confidence at 12% is nowhere near the 50% floor.

### Example 3: Risk-Off with Elevated VIX

```
SPY -0.9%     → -1
QQQ -1.3%     → -1
IWM -0.7%     → -1
VIX 26.10     → -1  (above 25)
VIX +8.2%     → -1  (above +5%)
DXY +0.5%     → -1  (above +0.3%)
TNX +0.9%     → -1  (above +0.8%)
BTC -3.1%     → -1  (below -2%)

net_score = -8  confidence = 1.00  → RISK_OFF  → DEFENSIVE_SHORT
```

---

## Recalibrating Thresholds

The regime model has not been backtested (V3 is the backtesting phase). The thresholds are grounded in market intuition, not optimized. If the model produces too many false RISK_ON signals or misses obvious risk-off moves, recalibrate using this process:

### Identifying a Miscalibrated Threshold

1. Pull recent audit records where `regime != expected`
2. Look at `vote_breakdown` for that run
3. Identify which vote cast a surprising direction
4. Check the raw input value vs the threshold

### The Right Way to Adjust

Change one threshold at a time. Document the change in `docs/regime_model.md` with the date and reason. Bad example: raising the SPY threshold from 0.3% to 0.5% because it voted +1 on three quiet days. Better example: raising it because you realize 0.3% is within the bid-ask spread of premarket quotes, making the signal noisy.

### Thresholds That Are Most Likely to Need Adjustment

- **VIX level 18/25**: These are long-standing technical levels. They held for decades. Resist changing them.
- **BTC thresholds**: The correlation between BTC and risk assets has been unstable. If BTC decouples from equities for an extended period (months), consider removing it from the model entirely rather than adjusting thresholds.
- **TNX thresholds**: Yield sensitivity to the stock market has been regime-dependent. In a rate-cutting cycle, yield and equity correlation may flip. Monitor and be prepared to remove TNX as a vote.

### Adding or Removing an Input

To add an input (e.g. credit spreads, copper):
1. Add a `_vote_{name}()` function in `regime.py` with the same ±1/0 interface
2. Add the `_cast()` call in `classify_regime()`
3. Update `_EXPECTED_VOTE_KEYS` in `gate_check()` to include the new key
4. Document in this file with the threshold rationale

To remove an input:
1. Remove the `_cast()` call — leave the function in place (don't break test references)
2. Update `_EXPECTED_VOTE_KEYS`
3. Note: `total_votes` will drop by 1, which affects confidence arithmetic

---

## Intraday Alert Triggers

The intraday monitor (`run_intraday.py`) fires Pushover alerts on:

| Trigger | Threshold | Alert type |
|---|---|---|
| Regime → CHAOTIC | `vix_change > +20%` in any 30-min interval | `chaotic` |
| Regime flip RISK_ON → RISK_OFF | `last_regime == RISK_ON and regime == RISK_OFF` | `regime_flip_risk_off` |
| Regime flip RISK_OFF → RISK_ON | `last_regime == RISK_OFF and regime == RISK_ON` | `regime_flip_risk_on` |

**Deduplication:** The same alert type is suppressed for 90 minutes after it fires. CHAOTIC can re-alert after 90 minutes if VIX remains elevated — this is intentional: a sustained CHAOTIC regime should re-alert rather than go silent.

Note: The intraday VIX spike threshold is **20%** (vs 15% for CHAOTIC in the premarket engine). The intraday monitor uses a higher bar because intraday VIX moves are noisier than daily moves.
