# Conflict Rules Engine

Version: 1.0  
Author: Dustin  
Scope: Core System Logic (Pre-Implementation)  
Status: Pre-Build Specification

## 1. Purpose

The Conflict Rules Engine defines how Signal Forge:

- detects disagreement between domains
- classifies disagreement into explicit conflict types
- resolves those conflicts into a deterministic execution posture

This is not a signal blending system.

Conflicts are:

- preserved
- made explicit
- resolved through rules

The engine must produce a deterministic and explainable transformation from:

- domain outputs
- unified thesis
- execution constraints

## 2. Design Principles

1. No averaging of signals
2. No hidden overrides
3. All conflicts must be classified
4. Resolution must produce execution implications
5. System must preserve asymmetry and nonlinearity
6. Output must be auditable and deterministic

## 3. Domain Input Contract

The conflict engine should consume a normalized domain envelope derived from the agent contract, not raw agent internals.

### Minimum input shape

```text
ConflictDomainInput
{
  domain: "macro" | "geo" | "market_quality" | "options"
  directional_bias: "bullish" | "bearish" | "neutral"
  conviction: float
  confidence: float
  key_drivers: [string]
  risks: [string]
  invalidation_conditions: [string]
  time_horizon: "intraday" | "swing" | "macro"
  special_flags: object | null
}
```

### Domain ownership assumptions

- `macro`
  Owns broad directional and regime posture.
- `geo`
  Owns geopolitical premium, event shock, and external stress translation.
- `market_quality`
  Owns tradability, liquidity health, and tape quality.
- `options`
  Owns nonlinear opportunity, path dependency, volatility asymmetry, and escape-window logic.

### Contract constraints

- Inputs must be fully attributable to a single domain.
- Missing or degraded domain coverage must be explicit before conflict evaluation starts.
- The conflict engine should never infer domain ownership from another domain’s output.

## 4. Conflict Detection

A conflict exists when at least one of the following is true:

1. `directional_bias` differs between domains.
2. `conviction` differs by `>= 0.4` in a way that changes posture.
3. `time_horizon` mismatch materially affects valid execution.
4. `special_flags` indicate opposing structural behavior.

### Detection notes

- Neutral vs directional is still a conflict candidate if the neutral domain owns a gating function.
- Not every conflict is directional. Tradability, timing, volatility, and nonlinear structure can conflict even if directional bias matches.
- Conflict detection should emit records even when the eventual resolution is only a dampener rather than a block.

## 5. Conflict Types

The system should classify every detected conflict into one or more explicit types.

### 5.1 Directional Conflict

Definition:
Two domains point in opposing directional terms.

Example:

- macro: bearish
- options: bullish

Execution implication:
Direction alone is insufficient. The engine must decide whether to dampen, split by timeframe, or allow a constrained tactical expression.

### 5.2 Conviction Conflict

Definition:
Two domains do not necessarily disagree on direction, but materially disagree on strength.

Example:

- macro conviction: `0.9`
- geo conviction: `0.4`

Execution implication:
Sizing and deployment urgency should be reduced before direction is changed.

### 5.3 Temporal Conflict

Definition:
Two domains express views on different horizons that cannot be executed identically.

Example:

- macro: bearish on `macro` horizon
- options: bullish on `intraday` horizon

Execution implication:
The engine should split valid behavior by timeframe rather than forcing one blended output.

### 5.4 Structural Conflict

Definition:
A nonlinear opportunity exists inside an opposing or hostile broader trend.

Example:

- macro: downtrend
- options: strong escape window

Execution implication:
Allow constrained tactical participation without claiming that the broader thesis has reversed.

### 5.5 Volatility Conflict

Definition:
Volatility conditions implied by one domain materially disrupt the assumptions of another domain.

Example:

- macro: stable
- geo: shock risk high

Execution implication:
Direction may remain intact, but structure and risk expression must change.

## 6. Special Flags

The options domain may emit special nonlinear flags that materially affect conflict resolution.

### Options special flags

```text
OptionsSpecialFlags
{
  escape_window_state: "strong" | "moderate" | "weak" | "none"
  iv_state: "expanding" | "contracting" | "elevated" | "compressed"
  liquidity_condition: "strong" | "thin"
  gamma_pressure: "high" | "low"
}
```

### Rules for special flags

- `escape_window_state` may justify tactical participation against the broader trend.
- `iv_state` changes structure preference, not just conviction.
- `liquidity_condition` can reduce tradability independent of directional agreement.
- `gamma_pressure` can alter path behavior and exit urgency even when directional posture is unchanged.

## 7. Resolution Mechanisms

The engine resolves conflicts through explicit rule families. Each applied rule must be visible in the audit trail.

### 7.1 Veto

A domain can block or sharply constrain execution when it owns a gating condition.

Example:

```text
IF geo.confidence > 0.8
AND geo.risks includes "event_shock"
THEN deployment_status = blocked
```

Veto domains in practice:

- `geo` for acute event shock
- `market_quality` for do-not-trade conditions
- `options` for hostile path and no escape window on leveraged expression

### 7.2 Dampening

Dampening preserves the base thesis while reducing force.

Example:

```text
IF macro.directional_bias = bearish
AND options.directional_bias = bullish
THEN conviction_adjustment = 0.6
AND sizing_posture = reduced
```

Use dampening when:

- disagreement weakens conviction but does not invalidate deployment
- risk is elevated but tradability still exists
- timing is uncertain but not blocked

### 7.3 Splitting

Splitting creates different valid behaviors across time horizons.

Example:

```text
IF macro.directional_bias = bearish
AND macro.time_horizon = macro
AND options.directional_bias = bullish
AND options.time_horizon = intraday
THEN intraday = allowed
AND swing = restricted
AND macro = bearish_base_case
```

Use splitting when:

- temporal conflict is the main issue
- the short-horizon opportunity does not invalidate the long-horizon thesis
- execution must distinguish tactical vs structural opportunity

### 7.4 Structure Override

This is the mandatory nonlinear rule.

```text
IF macro.directional_bias != options.directional_bias
AND options.special_flags.escape_window_state = "strong"
THEN allow_tactical_trade = true
AND sizing_posture = reduced
AND exit_plan_required = true
AND broader_macro_thesis_remains = true
```

Intent:

- preserve nonlinear edge
- allow temporary repricing opportunities
- avoid suppressing options structure under macro bias alone

### 7.5 Volatility Adjustment

Volatility conflict changes the valid form of expression.

Example:

```text
IF options.special_flags.iv_state = "expanding"
AND geo.risks includes "elevated_event_risk"
THEN favor_defined_risk_structures = true
AND structure_preference includes "spread"
```

Use volatility adjustment when:

- volatility expansion changes payoff asymmetry
- event risk increases gap risk
- outright directional expression becomes less efficient than defined-risk structures

## 8. Execution Posture Output

The conflict engine should emit an execution posture object that downstream execution consumes without reinterpretation.

### Output shape

```text
ConflictResolvedExecutionPosture
{
  execution_bias: "bullish" | "bearish" | "neutral"
  conviction_level: float
  tradability: "high" | "medium" | "low" | "blocked"
  allowed_timeframes: ["intraday" | "swing" | "macro"]
  structure_preference: ["debit_spread" | "credit_spread" | "outright" | "none"]
  risk_adjustments: [string]
  conflict_summary: {
    types: [string]
    dominant_domain: string
    suppressed_domains: [string]
    explanation: string
  }
}
```

### Output rules

- `execution_bias` reflects resolved posture, not averaged direction.
- `conviction_level` must reflect applied dampeners and unresolved conflicts.
- `tradability` can be low or blocked even when direction is clear.
- `allowed_timeframes` must be explicit when temporal splitting occurs.
- `structure_preference` should capture nonlinear and volatility-driven constraints.
- `conflict_summary` must explain why suppressed domains were constrained rather than silently discarded.

## 9. Resolution Flow

### Step 1

Collect all domain outputs.

### Step 2

Validate input completeness, coverage, and ownership tags.

### Step 3

Detect all conflicts.

### Step 4

Classify each conflict by type:

- directional
- conviction
- temporal
- structural
- volatility

### Step 5

Apply rule families in order:

1. veto
2. dampening
3. splitting
4. structure override
5. volatility adjustment

### Step 6

Generate resolved execution posture.

### Step 7

Attach explanation and audit trace.

## 10. Nonlinear Edge

The engine must explicitly preserve:

- escape window opportunities
- temporary repricing events
- volatility-driven price dislocations

These must never be suppressed by macro bias alone.

Design consequence:

Macro may remain the broader thesis owner while options still authorizes tactical, defined-risk participation under explicit constraints.

## 11. Failure States To Avoid

1. Signal averaging
2. Silent overrides
3. Ignoring options structure
4. Producing directional output without conflict explanation
5. Allowing execution to reinterpret signals

## 12. Out Of Scope

This module does not define:

- trade execution logic
- UI
- data ingestion

This module produces:

- execution constraints
- conflict explanations
- deterministic resolution artifacts

## 13. Success Criteria

The system should produce:

- consistent outputs for identical inputs
- clear conflict explanations
- actionable execution posture
- preserved nonlinear opportunity

## 14. Recommended Rule Records

For implementation readiness, each applied rule should be recorded in a structured trace.

```text
AppliedConflictRule
{
  rule_id: str
  rule_family: "veto" | "dampen" | "split" | "structure_override" | "volatility_adjustment"
  triggering_domains: [string]
  trigger_reason: str
  posture_effect: str
  audit_note: str
}
```

This ensures deterministic replay and clean human review.

## 15. Manual Review Checklist Before Build

- Does every detected conflict receive a named classification?
- Can a reviewer tell whether direction, timing, structure, or tradability changed?
- Are vetoes explicit and attributable to one owning domain?
- Can temporal conflicts create split behavior instead of forced consensus?
- Does options structure remain visible when it opposes macro direction?
- Does volatility conflict change structure preference rather than only confidence?
- Can Execution consume the output without reforming its own thesis?
- Would identical inputs always produce identical conflict records and posture output?
