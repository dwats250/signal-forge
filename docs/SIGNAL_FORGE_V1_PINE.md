# Signal Forge v1 Pine Engine

## Purpose

`signal_forge_v1.pine` is a TradingView indicator that qualifies intraday 0DTE momentum setups.

It is not an execution bot and it does not place trades. Its job is to:

- filter for approved tickers
- determine directional bias
- check whether price is interacting with an important level
- score the setup
- promote valid setups through a simple state machine
- emit one alert per setup lifecycle with the key context needed for review

The script is designed to support decision-making, not opaque automation.

## What The Engine Evaluates

The engine combines several intraday checks into one qualification process:

- Ticker universe: `SPY`, `QQQ`, `NVDA`, `TSLA`, `AMD`, `SMCI`, `META`, `MSTR`, `COIN`
- Session filter: open drive and power hour are valid; midday is blocked
- Bias filter: bullish requires `EMA9 > EMA21` and price above VWAP; bearish requires the inverse
- Key levels: opening range high/low, premarket high/low, previous day high/low, and VWAP
- Macro proxy: `SPY` references `QQQ`; everything else references `SPY`
- Volume condition: current volume relative to a rolling 60-minute normalized average
- Extension condition: distance from VWAP, with hard rejection when extension exceeds `1.5%`
- Movement condition: ATR floor
- Chop filter: suppresses structure scoring when the last 5 bars have too little net movement

## High-Level Flow

The indicator follows this sequence:

1. Build core intraday context from price, VWAP, EMAs, volume, and key levels.
2. Reject bars that fail hard filters such as invalid session, no level context, low liquidity, no bias, or overextension.
3. Score the remaining setup from `0` to `8`.
4. Move through a state machine: `SCAN -> SETUP -> TRIGGERED -> ALERTED -> EXPIRED`.
5. Fire one alert when a setup fully qualifies.
6. Expire the setup after invalidation or timeout, then reset back to scan mode.

## Scoring Model

Maximum score is `8`.

- `+2` Macro alignment
- `+2` Structure alignment when not choppy
- `+2` Volume expansion
- `+1` Not hard-extended from VWAP
- `+1` At key level

Important thresholds:

- `SCAN -> SETUP` requires `score >= 5`
- `TRIGGERED -> ALERTED` requires `score >= Alert Score Threshold`
- Default alert threshold input is `7`

## Key Levels

The indicator treats these as valid structural levels:

- Opening range high: `or_high`
- Opening range low: `or_low`
- Premarket high: `pm_high`
- Premarket low: `pm_low`
- Previous day high: `prev_day_high`
- Previous day low: `prev_day_low`
- VWAP: `vwap_val`

Price must be near a relevant level in the direction of bias for the setup to qualify.

## Trigger Types

There are two trigger paths.

### Breakout

A breakout requires:

- a defined active level
- directional bias
- a close through the active level
- the prior close on the opposite side of that level
- expanded volume
- bar close confirmation

This is intentionally close-based rather than wick-based.

### Retest

A retest is stricter than simple proximity to a level.

Bullish retest requires:

- prior close above the active level
- current bar low meaningfully probes the level area
- current close back above the level
- bullish confirmation on a closed bar

Bearish retest is the mirror image:

- prior close below the active level
- current bar high meaningfully probes the level area
- current close back below the level
- bearish confirmation on a closed bar

This keeps retest logic deterministic and avoids loose “price was near a level” behavior.

## State Machine

The engine uses a compact lifecycle:

- `SCAN`: watches for valid scored setups
- `SETUP`: setup is staged and level/bias are locked
- `TRIGGERED`: breakout or retest confirmation has occurred
- `ALERTED`: setup passed final threshold and emitted an alert
- `EXPIRED`: lifecycle ended due to timeout or invalidation

Once a setup becomes active, the script locks:

- `locked_level`
- `locked_bias`
- `locked_setup_type`

That lock is important because invalidation should not drift if the nearest live level changes later.

## Invalidation Logic

Invalidation is anchored to the locked level once the setup lifecycle is active.

- Bullish invalidation: `locked_level * 0.999`
- Bearish invalidation: `locked_level * 1.001`

The setup expires if price breaks that invalidation reference or if the lifecycle times out.

## Alert Behavior

The engine uses two alert mechanisms for TradingView compatibility:

- `alertcondition()` with a static message
- `alert(alert_msg)` for the full dynamic payload

Dynamic alert payload includes:

- ticker
- locked bias
- setup type
- score
- session label
- locked level
- invalidation
- extension percent
- volume ratio
- timestamp

Only one alert is emitted per setup lifecycle.

## Inputs

User-adjustable inputs:

- `Min ATR Threshold`
- `Alert Score Threshold`
- `Show Debug Labels`
- `Show Key Level Lines`
- `Show Session Background`

These let you tune strictness and display behavior without changing the engine structure.

## Visual Output

The indicator can render:

- EMA 9
- EMA 21
- session background shading
- key horizontal levels
- setup and triggered dots
- a fired-alert label
- a bottom-right debug table showing live engine state

The debug table is useful when validating why a setup did or did not progress.

## How To Use In TradingView

1. Open TradingView and create a new indicator script.
2. Paste the contents of [signal_forge_v1.pine](/home/dustin/signal-forge/signal_forge_v1.pine).
3. Save and add it to a 5-minute chart.
4. Use one of the approved tickers.
5. Keep the chart in the intended timezone context: `America/Los_Angeles` session logic is built into the script.
6. Review the debug table, state dots, and alert payload together instead of trading blindly from the alert alone.

## Recommended Operator Workflow

- Use the indicator during open drive and power hour.
- Watch for `SETUP` first, then confirm whether it progresses to `TRIGGERED` and `ALERTED`.
- Read the alert payload before acting.
- Verify that the locked level and invalidation make sense on the chart.
- Treat the script as a qualification engine, not a full trade plan.

## What This Engine Does Not Do

The script does not:

- place or manage orders
- size positions
- select options strikes or expirations
- evaluate broader portfolio risk
- replace discretionary operator review

It is a structured screening and alerting engine.

## File Reference

- Pine source: [signal_forge_v1.pine](/home/dustin/signal-forge/signal_forge_v1.pine)
