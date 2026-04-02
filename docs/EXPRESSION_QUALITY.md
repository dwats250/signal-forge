# Expression Quality Module

Version: 1.0  
Status: Architecture Definition Only (Deferred Implementation)  
Owner: Dustin

## 1. Purpose

Expression Quality is a first-class architectural component that evaluates how effectively a trading thesis can be expressed through a specific instrument, options chain, or structure.

This module does not form the thesis.
It evaluates the quality of expressing that thesis in the market.

## 2. Core Insight

A correct thesis can still lose money if expressed poorly.

Expression Quality exists to make that failure mode explicit by evaluating:

- liquidity constraints
- spread friction
- IV conditions
- positioning traps
- exit flexibility

This module is intended to prevent:

- getting stuck in illiquid chains
- entering structurally poor trades
- misreading distorted pricing as edge
- treating cheap-looking options as high-quality expression

## 3. Architectural Position

Expression Quality sits after thesis formation and conflict resolution, and before execution decisions.

### System flow

```text
Macro / Geo / Options Behavior / Market Quality
-> Thesis Engine
-> Conflict Rules
-> Expression Quality
-> Execution Interface
```

### Architectural consequence

- Thesis remains upstream and authoritative.
- Conflict Rules determine whether deployment is allowed and under what constraints.
- Expression Quality determines whether the allowed thesis can be expressed cleanly in a specific market vehicle.
- Execution consumes the filtered, expression-aware posture and selects candidate structures.

## 4. Boundary Definition

### 4.1 What Expression Quality Does

Evaluates:

- instrument suitability
- chain cleanliness
- structure viability
- exit flexibility
- trap risk

Produces:

- a structured tradability assessment
- expression-specific flags
- structure suitability guidance
- reasons the expression should be constrained or avoided

### 4.2 What Expression Quality Does Not Do

- does not generate trade ideas
- does not override thesis validity
- does not execute trades
- does not model live position state
- does not replace Options Behavior
- does not emit a single blended score

### 4.3 Separation From Options Behavior

Options Behavior owns:

- current nonlinear conditions
- IV expansion and compression
- skew dynamics
- unusual activity
- path dependency and escape-window logic

Expression Quality owns:

- whether a given chain or structure is usable
- whether the expression introduces avoidable friction
- whether execution quality degrades the underlying edge
- whether exit and adjustment flexibility is adequate for the thesis

### 4.4 Separation From Execution

Execution owns:

- selecting among allowed expressions
- sizing within thesis and risk constraints
- producing candidate trade structures
- enforcing operator and portfolio constraints

Expression Quality informs Execution, but does not choose the trade.

## 5. Evaluation Dimensions

Expression Quality should evaluate five dimensions.

### 5.1 Liquidity

Evaluates:

- bid/ask spread width
- volume
- open interest
- fill probability

Question answered:

Can this expression realistically be entered and exited without unacceptable friction?

### 5.2 Structure Integrity

Evaluates:

- strike spacing
- expiration alignment with thesis horizon
- payoff clarity
- gamma exposure profile

Question answered:

Does the proposed structure match the thesis cleanly, or does the structure itself introduce distortion?

### 5.3 Volatility Context

Evaluates:

- IV relative to realized movement
- IV expansion risk
- IV collapse risk

Question answered:

Is the option pricing environment supportive, neutral, or hostile for this expression?

### 5.4 Trap Risk

Evaluates:

- low liquidity combined with wide spreads
- IV distortion
- asymmetric fill risk
- inability to exit efficiently

Question answered:

Is this expression likely to trap the trader even if the thesis is directionally right?

### 5.5 Exit Flexibility

Evaluates:

- ease of partial exits
- ability to roll
- sensitivity to small price movements
- dependency on binary outcomes

Question answered:

Does this expression preserve room to manage the trade if conditions evolve?

## 6. Output Contract

This module must not output a single score.

It should return a structured object with discrete qualitative fields.

### Proposed output

```json
{
  "expression_quality": {
    "instrument_id": "string",
    "expression_target": "instrument | chain | structure",
    "liquidity": "strong | moderate | weak",
    "structure": "clean | acceptable | poor",
    "volatility": "favorable | neutral | unfavorable",
    "trap_risk": "low | medium | high",
    "exit_flexibility": "high | moderate | low",
    "tactical_only": true,
    "preferred_expression_types": [
      "debit_spread",
      "defined_risk_only"
    ],
    "flags": [
      "wide_spread",
      "low_oi",
      "iv_elevated"
    ],
    "summary": "short human-readable description"
  }
}
```

### Output rules

- `liquidity` describes friction quality, not market direction.
- `structure` describes fit between thesis and tradable structure.
- `volatility` describes pricing environment for the candidate expression.
- `trap_risk` is explicit and must never be buried in a summary label.
- `exit_flexibility` must remain visible even when liquidity appears acceptable.
- `tactical_only` should be true when the expression is only valid for narrow, high-attention use.
- `preferred_expression_types` may constrain Execution without selecting the exact trade.

## 7. Upstream Inputs

Expression Quality should consume:

- resolved thesis posture from the Thesis Engine
- deployment constraints from Conflict Rules
- current Options Behavior state
- relevant Market Quality context
- instrument and chain data needed to judge expression cleanliness

### Minimum architectural input view

```text
ExpressionQualityInput
{
  thesis_id: str
  execution_bias: str
  deployment_status: str
  timing_posture: str
  structure_constraints: [str]
  options_context: {
    vol_regime: str
    path_dependency_state: str
    escape_window_state: str
  }
  market_quality_context: {
    tradability_state: str
    liquidity_state: str
  }
  candidate_expression_context: {
    instrument_id: str
    expiration_profile: str
    spread_state: str
    open_interest_state: str
    volume_state: str
    strike_spacing_state: str
  }
}
```

## 8. Downstream Interface To Execution

Execution should receive the resolved expression-quality view, not raw microstructure analysis.

### Proposed execution-facing contract

```text
ExpressionQualityExecutionView
{
  expression_allowed: bool
  tactical_only: bool
  preferred_expression_types: [str]
  blocked_expression_types: [str]
  liquidity: str
  structure: str
  volatility: str
  trap_risk: str
  exit_flexibility: str
  flags: [str]
  summary: str
}
```

### Contract intent

- Execution should be told which expression families are suitable.
- Execution should not need to reinterpret raw spread, OI, or IV details.
- Expression Quality may narrow the valid menu without replacing Execution judgment.

## 9. Decision Logic Principles

Expression Quality should follow these rules:

1. A valid thesis does not imply a valid expression.
2. Poor exit flexibility can invalidate otherwise attractive structures.
3. Trap risk must remain explicit and reviewable.
4. Low-friction expression is preferable to seemingly cheaper but fragile expression.
5. Options Behavior may justify tactical participation, but Expression Quality decides whether the vehicle is usable.

## 10. Failure States To Avoid

1. Converting the module into a vibes-based ticker personality system
2. Hiding expression fragility inside a summary label
3. Duplicating Options Behavior instead of evaluating market usability
4. Emitting a single quality score that masks why the expression is poor
5. Allowing Execution to bypass the module and re-evaluate raw friction inputs

## 11. Deferred Implementation Notes

This module is intentionally not part of Core v1 implementation.

Reasons for deferral:

- the thesis and conflict contracts should be stabilized first
- candidate expression inputs are not yet formally modeled
- the boundary between chain-level and structure-level evaluation should be frozen before build

## 12. Open Design Questions

- Is the first implementation instrument-level, chain-level, or structure-level?
- Should the module evaluate one candidate structure at a time, or produce a filtered menu?
- Which flags are advisory, and which should be binding on Execution?
- How should trap risk and exit flexibility interact when they disagree?
- How much instrument baseline behavior belongs here versus a later Instrument Intelligence layer?

## 13. Recommendation

Expression Quality should be the next formal architecture PRD after the core thesis and conflict contracts are frozen for implementation.

It captures a real trading blind spot, has clear boundaries, and extends the system toward actual execution quality without forcing live trade-state logic into v1.
