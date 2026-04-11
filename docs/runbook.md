# Signal Forge V2 — Runbook

## When Does It Run

| Run | Schedule | Entry point |
|---|---|---|
| Premarket | 13:00 UTC (06:00 PT) Mon–Fri | `python -m signal_forge.run_premarket` |
| Intraday | Every 30 min, 14:00–21:00 UTC Mon–Fri | `python -m signal_forge.run_intraday` |
| Manual | GitHub Actions → "Signal Forge V2" → Run workflow | choose `premarket` or `intraday` |

The premarket run is what matters for the day's setup decisions. The intraday monitor only fires Pushover alerts on regime shifts — it does not re-qualify trades.

---

## Reading the Morning Report

Reports land in two places simultaneously:

1. **GitHub** — `reports/YYYY-MM-DD.md` committed to `main`
2. **Pushover** — push notification to your phone

### Report Header

```
══ SIGNAL FORGE ──── 2026-04-14 (Mon) ══
  Regime: RISK_ON       Posture: AGGRESSIVE_LONG    Confidence: 75%
  VIX: 16.40 (-4.20%)  DXY: 97.10 (-0.90%)  TNX: 4.15 (-1.40%)  BTC: +2.30%
```

- **Regime**: The classified market state. Only `RISK_ON` and `RISK_OFF` produce trade candidates.
- **Posture**: The execution stance. `AGGRESSIVE_LONG` = full size, `CONTROLLED_LONG` = half size mentally. `STAY_FLAT` = nothing to act on, move on.
- **Confidence**: `abs(net_score) / 8 votes`. Below 50% → STAY_FLAT regardless of regime. At 75% → at least 6 of 8 inputs agree. At 100% → unanimous.

### What Each Posture Means

| Posture | What to do |
|---|---|
| `AGGRESSIVE_LONG` | RISK_ON, ≥75% confidence. Size up per the expression. |
| `CONTROLLED_LONG` | RISK_ON, 50–74% confidence. Valid setups, but regime is moderate. |
| `NEUTRAL_PREMIUM` | TRANSITION, VIX 18–25. Sell premium on range-bound names only. |
| `DEFENSIVE_SHORT` | RISK_OFF, ≥55% confidence. Bear structures and short expressions only. |
| `STAY_FLAT` | All other cases. Do not trade. Close losers if any. |

### Validated Trades Section

A TRADE appears when all 9 gates passed. Example:

```
■ VALIDATED TRADES (1)

  NVDA   LONG   Bull Put Spread
  Entry 188.63  Stop 178.77  Target 208.35
  Strikes: sell $188p / buy $187p  |  DTE: 14–21
  Size: 1 contract  |  Max risk: $100
  Exit: +50% of premium received  |  Loss: full credit loss
  IV: ELEVATED_IV  |  Structure: TREND
```

Fields to check before execution:
- **Entry** — the current price used for planning. Verify it hasn't moved significantly.
- **Stop / Target** — derived from ATR14. Not meant to be order prices; they define the R:R ratio.
- **Strikes** — relative to ATM at time of run. Verify against live chain before entering.
- **DTE range** — select the nearest expiry that falls inside this window.
- **Max risk** — the dollar amount you're risking if the spread goes to max loss.
- **Exit rule** — non-negotiable. Close at +50% or let it expire worthless. No adjustments.

### Watchlist Section

A WATCHLIST entry passed all critical gates but failed exactly one non-critical gate:

```
~ META    LONG    entry=629.86  |  earnings_clear: earnings 2026-04-17 within 5d window
```

This is a real setup with one condition outstanding. The condition is stated explicitly. Check back when the condition is resolved (e.g., after earnings, or when R:R improves).

### CHOP Section

These tickers were structurally disqualified — EMA not aligned and/or momentum flat. Not worth tracking today.

### Data Status Footer

```
VIX ✓  DXY ✓  TNX ✓  BTC ✓  SPY ✓  QQQ ✓  IWM ✓
Symbols: 20 valid / 0 invalid  |  Source: yfinance
```

If any symbol shows `✗` and it's in the required tier (`^VIX`, `DX-Y.NYB`, `^TNX`, `SPY`, `QQQ`), the pipeline would have halted. A `✗` on an optional symbol means that ticker was excluded from analysis.

---

## What to Do on a NO TRADE Day

1. Read the regime/posture. Understand why.
2. Check the watchlist — any setup close to qualifying?
3. Check the CHOP log — if every ticker is CHOP, structure is broken market-wide. Stay flat.
4. Nothing to do. Flat is a position.

---

## What to Do When the System Halts

A halt means a required macro symbol (VIX, DXY, TNX, SPY, or QQQ) failed validation. The terminal shows:

```
⚠  SYSTEM HALT — MACRO DATA INVALID
Failed symbol: ^VIX (reason: age 847s exceeds 300s threshold)
DO NOT TRADE — DATA UNTRUSTWORTHY
```

The commit message in this case is `SF HALT: YYYY-MM-DD | DATA INVALID | {symbol}`.

**What to check:**

1. **Is it market hours?** If the halt occurs before market open (pre-6am PT), price data is often stale — this is expected. Wait for the scheduled premarket run at 6am.

2. **Is yfinance down?** Go to `finance.yahoo.com` and verify live quotes manually. If the site is down, the system will self-heal on the next scheduled run.

3. **Is the symbol bound outdated?** Check `validation.py:PRICE_BOUNDS`. If e.g. SPY has moved beyond the configured bounds, update them. This happened in Phase 2 when QQQ exceeded $600.

4. **Trigger a manual run** once the issue is resolved:
   - GitHub → Actions → "Signal Forge V2" → Run workflow → select `premarket`

---

## Triggering a Manual Run

### From GitHub (recommended)

1. Go to the repo → Actions tab → "Signal Forge V2"
2. Click "Run workflow"
3. Select branch: `main`
4. Mode: `premarket` for a full run, `intraday` for a regime check
5. Click "Run workflow"
6. Watch the "Premarket Pipeline" or "Intraday Monitor" job

### From Local Terminal

```bash
cd ~/signal-forge
python -m signal_forge.run_premarket   # full pipeline
python -m signal_forge.run_intraday    # regime check only
```

For local runs, set environment variables first:

```bash
export POLYGON_API_KEY="your_key"
export PUSHOVER_USER_KEY="your_user_key"
export PUSHOVER_API_KEY="your_app_token"
```

Or create a `.env` file (already in `.gitignore`):

```
POLYGON_API_KEY=...
PUSHOVER_USER_KEY=...
PUSHOVER_API_KEY=...
```

---

## Reading audit.jsonl

Every run appends one JSON record. Premarket records look like:

```json
{
  "chop_count": 8,
  "confidence": 0.75,
  "date_local": "2026-04-14",
  "elapsed_seconds": 12.4,
  "net_score": 6,
  "output_paths": ["reports/2026-04-14.md"],
  "posture": "AGGRESSIVE_LONG",
  "pushover_sent": true,
  "pushover_error": null,
  "regime": "RISK_ON",
  "rejected_count": 12,
  "run_id": "abc123...",
  "symbols_valid": 20,
  "symbols_invalid": 0,
  "timestamp_utc": "2026-04-14T13:02:14.000000+00:00",
  "total_votes": 8,
  "trade_count": 2,
  "tradeable": true,
  "vix_change": -0.042,
  "vix_level": 16.4,
  "watchlist_count": 1
}
```

Intraday records have `"run_type": "intraday"` and add `"alert_fired"` (null or an alert type string).

**Useful one-liners:**

```bash
# All runs with at least one trade
grep '"trade_count"' logs/audit.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    r = json.loads(line)
    if r.get('trade_count', 0) > 0:
        print(r['date_local'], r['regime'], r['trade_count'], 'trade(s)')
"

# All halts
grep '"SF HALT"' logs/audit.jsonl

# Last 5 runs
tail -5 logs/audit.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    r = json.loads(line)
    print(r.get('date_local','?'), r.get('run_type','premarket'), r['regime'], r['posture'], f\"conf={r['confidence']:.0%}\")
"

# All intraday alerts that fired
python3 -c "
import json
for line in open('logs/audit.jsonl'):
    r = json.loads(line)
    if r.get('alert_fired'):
        print(r['timestamp_utc'], r['alert_fired'], r['regime'])
"
```

---

## Extending the System

### Adding a new symbol

1. Add it to `UNIVERSE` in `ingestion.py`
2. Add price bounds in `validation.py:PRICE_BOUNDS`
3. Run locally and verify it passes validation
4. If it's a macro driver that should halt the pipeline, add it to `HALT_SYMBOLS`

### Updating price bounds

Bounds in `validation.py:PRICE_BOUNDS` are sanity checks, not forecasts. Update them when:
- A symbol has moved significantly (e.g. QQQ exceeded the $600 upper bound)
- A corporate action (split, merger) changes the price range

Rule: bounds should catch obviously wrong data (QQQ at $6 or $6000), not normal market appreciation. Give them 2–3× headroom from current price on each side.

### Changing the regime schedule

Edit `.github/workflows/signal_forge.yml`. The `schedule:` block uses standard cron syntax (UTC). GitHub Actions delays scheduled runs by up to 30 minutes during high load.
