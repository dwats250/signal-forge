# Signal Forge V2 — Options Framework

## Overview

The options layer translates a qualified trade setup (direction, entry, ATR-derived stops) into a specific options expression. It does not make market calls — that happened in layers 1–7. It answers a narrower question: given a confirmed directional setup, what is the optimal options structure for this IV environment?

Output: a single strategy per ticker with specific strikes, DTE range, sizing, and exit rules.

---

## Strategy Selection Matrix

Strategy is determined by two inputs only: **trade direction** and **IV environment**.

| Direction | IV Environment | Strategy | Rationale |
|---|---|---|---|
| LONG | LOW_IV | `long_call_spread` | Debit spread. Low IV means options are cheap — pay a small debit for defined upside. Credit spreads in low IV collect too little premium to be worth the obligation. |
| LONG | NORMAL_IV | `bull_put_spread` | Credit spread. Sell an OTM put below the stop, collect premium. At normal IV, the premium collected is meaningful. |
| LONG | ELEVATED_IV | `bull_put_spread` | Credit spread. Higher IV → more premium. Selling put spreads below support is the preferred expression when IV is elevated. |
| LONG | HIGH_IV | `bull_put_spread` | Credit spread, but 50% size reduction. High IV means premium is rich but the environment is risky. Collect premium at reduced size. |
| SHORT | LOW_IV | `long_put_spread` | Debit spread. Buy the put direction outright via spread. Low IV = cheap directional bets. |
| SHORT | NORMAL_IV | `bear_call_spread` | Credit spread. Sell calls above resistance, collect premium on the short thesis. |
| SHORT | ELEVATED_IV | `bear_call_spread` | Credit spread. Same as NORMAL_IV but richer premium. |
| SHORT | HIGH_IV | `bear_call_spread` | Credit spread, 50% size reduction. Same caution as LONG/HIGH_IV. |

### Why the asymmetry between LOW_IV and everything else?

In LOW_IV (VIX < 15), implied volatility is priced cheaply enough that **buying** the directional exposure via debit spreads is better value than selling credit. A bull put spread in low IV collects $0.15–0.30 per $1 width — not worth the obligation. A long call spread in the same environment costs $0.30–0.50 per $1 width and captures the full directional move. The crossover point is approximately IV = 15–16%, which is why `LOW_IV` ends at 15.

---

## IV Environment Classification

IV is approximated by the current VIX level (for all equity symbols). VIX is used as a proxy, not actual per-symbol implied volatility.

| IV Environment | VIX Level | Meaning |
|---|---|---|
| `LOW_IV` | < 15 | Complacent market. Options cheap. Prefer debit spreads. |
| `NORMAL_IV` | 15 – 20 | Baseline environment. Credit spreads are the default. |
| `ELEVATED_IV` | 20 – 28 | Fearful market. Premium is rich. Credit spreads are better. |
| `HIGH_IV` | > 28 | High stress. Premium is very rich but environment is volatile. Trade at 50% size. |

**Note:** The VIX level check for IV environment uses the live VIX reading from regime data, not a symbol-specific IV. This is a simplification. A stock with elevated earnings IV but low VIX would be misclassified as LOW_IV. The system does not currently model per-symbol IV.

---

## Strike Selection

Strikes are defined **relative to the current price at time of run** (not live market). Always verify against the live options chain before entry.

### Credit Spreads (bull_put_spread, bear_call_spread)

```
bull_put_spread:
  short_strike = floor(entry - 1 × ATR14)  ← ATM-ish put, near the stop level
  long_strike  = short_strike - spread_width

bear_call_spread:
  short_strike = ceil(entry + 1 × ATR14)   ← ATM-ish call, near the stop level
  long_strike  = short_strike + spread_width
```

The short strike is placed near the **stop level** (1× ATR14 from entry). This means: if the trade goes to the stop, the short option is approximately ATM. If price never reaches the stop, the entire spread expires worthless (full credit retained).

### Debit Spreads (long_call_spread, long_put_spread)

```
long_call_spread:
  long_strike  = ceil(entry)         ← ATM or just in-the-money
  short_strike = long_strike + spread_width

long_put_spread:
  long_strike  = floor(entry)        ← ATM or just in-the-money
  short_strike = long_strike - spread_width
```

The long leg is placed ATM to capture full directional movement. The short leg caps maximum gain at `spread_width × 100` per contract, which is the trade-off for reducing cost.

### Spread Width

Working spread width is `$1.00` for all symbols. Width is capped by symbol tier:

| Symbol | Max Spread Width |
|---|---|
| SPY, QQQ, IWM | $5.00 |
| All others | $2.50 |

The cap exists to prevent spreads wider than what the $150 budget can cover at 1 contract. In practice, at $1.00 working width, sizing produces 1 contract for all symbols.

---

## Expiry (DTE) Selection

DTE range is determined by the ticker's 5-day momentum.

| |momentum_5d| | DTE Range | Reasoning |
|---|---|---|
| > 5% | 7 – 14 days | Strong momentum — use short DTE to maximize theta and avoid mean reversion. |
| > 2% | 14 – 21 days | Moderate momentum — standard window for premium strategies. |
| ≤ 2% | 21 – 30 days | Low momentum — longer DTE gives the thesis more time to develop. |

**This is a range, not an exact expiry.** Select the nearest standard expiry that falls within the specified range. If no expiry falls within range (e.g. a thin options market), the nearest available expiry outside the range is acceptable — note this as a deviation.

---

## Sizing

Base formula:

```python
contracts = floor(150 / (spread_width * 100))
```

At `$1.00` spread width:
- `floor(150 / 100) = 1` contract
- Actual risk: $100 (the debit paid or max loss on the credit spread)

HIGH_IV adjustment (50% size reduction):

```python
if iv_environment == "HIGH_IV":
    contracts = floor(contracts / 2)
```

At 1 base contract, this produces 0 — the expression is **dropped entirely**. This only affects tickers where base sizing produces ≥ 2 contracts (spread width ≤ $0.75). In practice at $1.00 width, HIGH_IV expressions will not appear in output. This is intentional: HIGH_IV + a single contract is not worth the commission cost in most brokerage structures. If you want HIGH_IV trades, widen the risk budget in `options.py`.

**Max risk is always explicitly stated in output.** Never enter more contracts than shown.

---

## Exit Rules

Exit rules are uniform across all strategies and are non-negotiable:

| Event | Action |
|---|---|
| Credit spread reaches 50% of max credit received | Close for profit |
| Debit spread reaches 50% of max potential gain | Close for profit |
| Spread goes to full max loss | Close (do not adjust) |
| Expiry approached without trigger | Let expire worthless (credit) or close (debit) |

**No adjustments.** Do not roll strikes. Do not convert to calendar or ratio spreads. The qualification process does not model adjusted positions. If a spread is going against you, let it go to max loss rather than risk undefined outcomes.

**Why +50% profit target?** Defined-risk spreads have a bounded payoff profile. Holding for maximum profit requires being right directionally to expiry. Taking 50% off the table when available gives up the final 50% of theoretical max in exchange for eliminating time risk, theta drag, and IV crush on profitable positions.

---

## What Each Strategy Means

### `bull_put_spread`

Sell an OTM put, buy a further OTM put. Net credit received at entry.

- **You win if:** price stays above the short strike at expiration.
- **You lose if:** price falls to or below the long strike.
- **Max gain:** credit received (retain 100% if spread expires worthless).
- **Max loss:** `(spread_width × 100) - credit received` per contract.
- **Best for:** LONG thesis in a stock that you believe won't fall below support.

Example: NVDA at $188, stop $179. Sell $179p / buy $178p for $0.35 credit. Keep $35 if NVDA stays above $179 at expiry. Lose $65 if NVDA drops below $178.

---

### `long_call_spread`

Buy an ATM call, sell a further OTM call. Net debit paid at entry.

- **You win if:** price rises above the short strike at expiration.
- **You lose if:** price doesn't move up or falls.
- **Max gain:** `(spread_width × 100) - debit paid` per contract.
- **Max loss:** debit paid per contract.
- **Best for:** LONG thesis in LOW_IV — options are cheap, pay a small debit for upside.

Example: NVDA at $188, target $207. Buy $188c / sell $189c for $0.45 debit. Max gain $55 if NVDA closes above $189 at expiry. Max loss $45.

---

### `bear_call_spread`

Sell an OTM call, buy a further OTM call. Net credit received at entry.

- **You win if:** price stays below the short strike at expiration.
- **You lose if:** price rises to or above the long strike.
- **Max gain:** credit received.
- **Max loss:** `(spread_width × 100) - credit received` per contract.
- **Best for:** SHORT thesis — sell calls above resistance.

---

### `long_put_spread`

Buy an ATM put, sell a further OTM put. Net debit paid at entry.

- **You win if:** price falls below the short strike at expiration.
- **You lose if:** price doesn't fall or rises.
- **Max gain:** `(spread_width × 100) - debit paid` per contract.
- **Max loss:** debit paid per contract.
- **Best for:** SHORT thesis in LOW_IV — pay a small debit for downside.

---

## Before Entering a Trade

1. **Verify the entry price.** The report shows price at time of run (premarket). If the market has moved significantly since 6am, recalculate stops and strikes.

2. **Verify strikes against the live chain.** Options chains update continuously. The system computes strikes from ATR; the actual best strike may be one increment away from what the report shows.

3. **Verify DTE.** The report shows a DTE range. Select the specific expiry that falls inside that window with sufficient open interest.

4. **Check bid-ask spread.** For low-liquidity names (PAAS, GDX), wide bid-ask spreads can turn a positive EV trade negative. If the spread is more than 20% of the credit/debit, reconsider.

5. **Confirm IV environment.** VIX moves during the morning. If VIX has crossed a threshold (e.g. from NORMAL_IV 19 to LOW_IV 14) since the report ran, the recommended strategy may need to flip.

---

## Debugging Expression Output

### "No expressions generated" on a TRADE day

Check: `qualify_all()` output. If all TRADE-status tickers fail at the expression stage, the most likely cause is HIGH_IV 50% size reduction producing 0 contracts. Also check if ATR14 is extremely high (ATR > 8% of price fails gate 6 before reaching the options layer).

### Strategy doesn't match expected

The strategy matrix is purely mechanical. If you expect `bull_put_spread` but see `long_call_spread`, VIX dropped below 15 (LOW_IV threshold) since the last review. The IV environment classification is updated on every run.

### Strikes seem wrong

Verify `entry` in the report — it's the price at fetch time, not the current price. If NVDA moved from $188 to $195 between 6am and your entry, the reported strikes are stale. Recalculate from current price.

### DTE range not available

Some symbols have monthly options only. If the computed DTE range (e.g. 7–14 days) falls between two monthly expiries, select the closer one. This is a known limitation of the system — it assumes weekly options availability.
