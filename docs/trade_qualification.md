# Signal Forge V2 — Trade Qualification

## Overview

Every ticker in the universe passes through a 9-gate sequential filter. Gates are evaluated in order. A ticker either passes all 9 (TRADE), fails one non-critical gate (WATCHLIST), or fails more (REJECTED). The output is a small, high-confidence candidate list — not a ranked list, not a score.

**Key principle:** The gates do not score or weight. Each gate is binary. The first critical failure is an immediate rejection. There is no recovery from a critical gate failure.

---

## Gate Sequence

### Critical Gates (1–4) — Immediate Rejection on Failure

Failure at any critical gate produces `status = REJECTED` immediately. The remaining gates are not evaluated.

---

#### Gate 1 — REGIME_TRADEABLE

```python
if not regime.tradeable:
    REJECT("posture is STAY_FLAT or CHAOTIC")
```

`regime.tradeable` is `False` when posture is `STAY_FLAT` or regime is `CHAOTIC`. On these days, the system short-circuits the entire qualification engine: every ticker is rejected at gate 1. No options expressions are generated. The output is a NO TRADE report.

This is the most important gate. If the regime doesn't support trading, nothing else matters.

---

#### Gate 2 — CONFIDENCE

```python
if regime.confidence < 0.50:
    REJECT("confidence below 0.50 floor")
```

The 0.50 floor means at least 4 of 8 inputs must agree on direction. Below this, the regime classification is statistically indistinguishable from noise. Note: this gate is somewhat redundant with gate 1 — a regime with confidence < 0.50 already produces `STAY_FLAT` via the posture mapping. Gate 2 is a belt-and-suspenders check for edge cases.

---

#### Gate 3 — DIRECTION_MATCH

```python
if not _direction_matches_regime(direction, regime):
    REJECT("trade direction conflicts with regime")
```

Direction is inferred from the structure reading:

| Classification | Direction Logic |
|---|---|
| TREND (bull alignment) | LONG |
| TREND (bear alignment) | SHORT |
| PULLBACK | Follows alignment direction |
| BREAKOUT | Follows momentum sign (positive → LONG, negative → SHORT) |
| REVERSAL | Opposes alignment (bull alignment → SHORT) |

Direction must match regime:
- `RISK_ON` → only LONG setups pass
- `RISK_OFF` → only SHORT setups pass
- `TRANSITION` → **nothing passes** (this gate always fails for TRANSITION)

If direction cannot be determined, gate fails.

---

#### Gate 4 — STRUCTURE

```python
if reading.classification == "CHOP":
    REJECT("no tradeable structure")
```

Any ticker classified as CHOP is disqualified here. CHOP means: EMAs not aligned in any direction AND 5-day momentum is below ±0.5%. There is no setup to express. This gate catches tickers that passed regime screening but have no structural edge of their own.

---

### Non-Critical Gates (5–9) — One Miss Allowed

For gates 5–9, the system tracks failures. If exactly **1** of these gates fails, the ticker is placed on the WATCHLIST with the failed gate name as the `watchlist_condition`. If **2 or more** fail, the ticker is REJECTED.

---

#### Gate 5 — STOP_DEFINED

```python
if metrics.atr14 is None:
    FAIL("ATR14 not available — stop cannot be defined")
```

Stop and target are derived from ATR14. If OHLCV history was unavailable or too short (< 21 bars), ATR14 is `None`. Without a stop, no trade can be sized or risk-managed. This gate almost always fails together with gate 4 (CHOP from `sufficient_history = False`), making it rare in practice.

---

#### Gate 6 — STOP_DISTANCE

```python
stop_distance_pct = atr14 / price
if stop_distance_pct > 0.08:
    FAIL("stop > 8% — risk too wide for defined-risk spread")
```

Stop is defined as **1× ATR14 below entry** (long) or above entry (short). If ATR14 / price > 8%, the stop is too wide to be expressed as a defined-risk spread within the sizing budget. Tickers with very high volatility or thin float often fail here.

The 8% threshold is not arbitrary: at $150 max risk and a $100 max spread contract, an 8% stop on a $50 stock is $4 — which maps to a $4-wide spread requiring 0 contracts at the sizing formula.

---

#### Gate 7 — RISK_REWARD

```python
if risk_reward < 2.0:
    FAIL("R:R below 2.0 minimum")
```

Stop = 1× ATR14, Target = 2× ATR14. This gives R:R = 2.0 by construction, so this gate will never fail under normal operation. It exists as a sanity check against corrupted ATR values or future changes to the stop/target formula.

If you're debugging a WATCHLIST entry with `gates_failed = ["risk_reward"]`, look at the raw ATR value — something is wrong upstream.

---

#### Gate 8 — POSITION_SIZE

```python
contracts = floor(150 / (spread_width * 100))
if contracts < 1:
    FAIL("cannot size: 0 contracts at max risk $150")
```

The sizing formula: maximum $150 per trade, spread width in dollars.

- `$1.00` spread → `floor(150/100) = 1` contract ($100 risk)
- `$1.50` spread → `floor(150/150) = 1` contract ($150 risk)
- `$2.00` spread → `floor(150/200) = 0` contracts → FAIL

Default working spread width is `$1.00` for most equities, giving 1 contract at $100 risk. SPY/QQQ/IWM have a cap of `$5.00` max spread width, other symbols cap at `$2.50`. A ticker fails here when its price is so low that a 1-contract spread at the minimum width still exceeds the $150 budget — this is rare.

---

#### Gate 9 — EARNINGS

```python
next_earnings = _get_earnings_date(symbol)
if next_earnings and abs((next_earnings - today).days) <= 5:
    FAIL("earnings within 5-day window")
```

Options strategies are not entered within 5 calendar days of earnings. IV expansion from earnings creates unpredictable outcomes that override technical analysis. The gate uses yfinance's earnings calendar.

**Fail-open behavior:** If yfinance cannot provide earnings data for a symbol, the gate passes. This is intentional — a missing calendar is not a reason to reject a real setup. Check the watchlist condition if you want to verify.

---

## Stop and Target Formula

```
stop   = entry - (1 × ATR14)   [long]
stop   = entry + (1 × ATR14)   [short]
target = entry + (2 × ATR14)   [long]
target = entry - (2 × ATR14)   [short]
```

R:R is always **2.0**. This is not adjustable.

**Stop and target are planning levels, not order prices.** They define the ratio. Before entering a trade, verify that the options spread can actually achieve this R:R at current market prices. The qualification engine does not look at live options chains.

**ATR14 is Wilder's RMA** (exponential with alpha=1/14, `adjust=False`). This matches TradingView's ATR calculation. Simple rolling average (pandas default) will give different results, especially on short history.

---

## Position Sizing

```python
contracts = floor(150 / (spread_width * 100))
```

Max risk per trade is capped at **$150**. For a $1.00-wide spread:

| Spread Width | Contracts | Actual Risk |
|---|---|---|
| $1.00 | 1 | $100 |
| $1.25 | 1 | $125 |
| $1.50 | 1 | $150 |
| $2.00 | 0 | → rejected |

HIGH_IV environment applies an additional 50% size reduction (applied after contract sizing):

```python
if iv_environment == "HIGH_IV":
    contracts = floor(contracts / 2)
    if contracts < 1:
        # expression is dropped entirely
```

This is the only case where a successfully sized trade can be dropped at the expression stage rather than at qualification.

---

## Watchlist Logic

```
1 non-critical gate fails  → WATCHLIST  (watchlist_condition = gate name)
2+ non-critical gates fail → REJECTED
any critical gate fails    → REJECTED
```

A WATCHLIST entry is a real setup with one condition outstanding. The condition is always stated explicitly in the report:

```
~ META    LONG    entry=629.86  |  earnings_clear: earnings 2026-04-17 within 5d window
```

Check back when the condition resolves. Do not trade a WATCHLIST entry — it has not passed all 9 gates.

---

## Rejection Reason Taxonomy

| Reason | Gate | What it means |
|---|---|---|
| `posture is STAY_FLAT or CHAOTIC` | 1 | Regime not tradeable — nothing trades today |
| `confidence below 0.50 floor` | 2 | Regime vote too split to act on |
| `trade direction conflicts with regime` | 3 | Ticker wants to go the wrong way for today's market |
| `no tradeable structure` | 4 | CHOP — EMA and momentum don't support a setup |
| `ATR14 not available` | 5 | Insufficient price history; can't define a stop |
| `stop > 8%` | 6 | Ticker is too volatile for defined-risk spread at budget |
| `R:R below 2.0` | 7 | Sanity check — should not occur in practice |
| `cannot size: 0 contracts` | 8 | Spread too wide for $150 budget |
| `earnings within 5d window` | 9 | Event risk override |

---

## Worked Examples

### Example 1: TRADE (all 9 gates pass)

**Context:** RISK_ON, AGGRESSIVE_LONG, confidence 0.75. NVDA in TREND with bull EMA alignment.

```
Gate 1 REGIME_TRADEABLE:  regime.tradeable = True              PASS
Gate 2 CONFIDENCE:         0.75 >= 0.50                         PASS
Gate 3 DIRECTION_MATCH:    TREND(bull) → LONG, regime=RISK_ON   PASS
Gate 4 STRUCTURE:          TREND ≠ CHOP                         PASS
Gate 5 STOP_DEFINED:       ATR14 = 9.42                         PASS
Gate 6 STOP_DISTANCE:      9.42 / 188.63 = 5.0% < 8%           PASS
Gate 7 RISK_REWARD:        R:R = 2.0                            PASS
Gate 8 POSITION_SIZE:      floor(150/100) = 1 contract          PASS
Gate 9 EARNINGS:           next earnings 30 days away           PASS

→ TRADE
   entry=188.63  stop=179.21  target=207.47
   strategy: bull_put_spread (ELEVATED_IV)
   1 contract | max risk $100
```

---

### Example 2: WATCHLIST (gate 9 fails)

**Context:** Same regime. META in TREND with bull EMA alignment.

```
Gate 1–8: all pass
Gate 9 EARNINGS: earnings in 3 days — within 5d window         FAIL

→ WATCHLIST  |  watchlist_condition: earnings_clear
  "earnings 2026-04-13 within 5d window"
```

Check back after earnings. If META holds structure and IV settles, it will qualify on the next run.

---

### Example 3: REJECTED (gate 3 fails — TRANSITION regime)

**Context:** TRANSITION, NEUTRAL_PREMIUM. SPY in TREND with bull EMA alignment.

```
Gate 1 REGIME_TRADEABLE: True (NEUTRAL_PREMIUM is tradeable)   PASS
Gate 2 CONFIDENCE:        passes
Gate 3 DIRECTION_MATCH:   TRANSITION → nothing matches          FAIL (critical)

→ REJECTED  |  rejection_reason: trade direction conflicts with regime
```

TRANSITION regime never produces directional setups. NEUTRAL_PREMIUM posture is for premium selling only, and the qualification engine does not currently model non-directional setups.

---

### Example 4: REJECTED (multiple non-critical gates fail)

**Context:** RISK_ON. PAAS with ATR14 = 1.45, price = 12.30, earnings in 4 days.

```
Gate 1–4: all pass
Gate 5 STOP_DEFINED:   ATR14 = 1.45                             PASS
Gate 6 STOP_DISTANCE:  1.45 / 12.30 = 11.8% > 8%              FAIL
Gate 7 RISK_REWARD:    R:R = 2.0                               PASS
Gate 8 POSITION_SIZE:  passes
Gate 9 EARNINGS:       earnings in 4 days                      FAIL

→ REJECTED  |  2 non-critical failures (stop_distance + earnings_clear)
```

Two fails in gates 5–9 → REJECTED. Would have been WATCHLIST if only one had failed.

---

## Extending the Qualification Engine

### Adding a Gate

1. Define a constant: `GATE_NEW_CONDITION = "new_condition"`
2. Add the check in `qualify_one()` using the `pass_()` / `fail_()` helper pattern
3. Decide: critical (return immediately on fail) or non-critical (append to fails list)
4. If non-critical, document the watchlist condition string — it prints verbatim in the report
5. Update `_EXPECTED_GATE_NAMES` if one exists

### Changing Stop or Target

The system uses 1× and 2× ATR14. If you want to change this (e.g. 1.5× stop), change `_compute_setup()` in `qualification.py`. Also update:
- Gate 6 threshold (8% is calibrated against 1× ATR)
- Gate 8 sizing logic if risk budget changes
- This documentation

The gates are a chain. Changing one often requires reviewing the downstream ones.
