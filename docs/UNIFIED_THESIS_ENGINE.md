# Unified Thesis Engine

## Purpose

The Unified Thesis Engine defines the system contract that transforms domain-specific agent outputs into one coherent, reviewable thesis state without collapsing domain edge into a blended score.

This document is an architecture specification only. It does not define production code, live trading rules, or auto-learning behavior.

## 1. Unified Thesis State Schema

The unified thesis state should be a structured object with six layers:

1. Metadata
2. Domain outputs
3. Cross-domain synthesis
4. Conflict map
5. Execution-ready state
6. Audit and learning hooks

### Proposed schema

```text
UnifiedThesisState
{
  thesis_id: str
  created_at: datetime
  as_of: datetime
  version: str
  universe: {
    symbol: str
    venue: str | null
    timeframe: str
    session_context: str
  }
  build_context: {
    data_cutoff: datetime
    input_snapshot_id: str
    normalization_version: str
    engine_version: str
  }
  domain_outputs: {
    macro_regime: AgentOutput
    geopolitical_premium: AgentOutput
    market_quality: AgentOutput
    options_behavior: AgentOutput
  }
  synthesis: {
    thesis_state: "aligned" | "mixed" | "conflicted" | "blocked"
    directional_posture: "pro-risk" | "risk-off" | "neutral" | "two-sided" | "selective"
    conviction: {
      level: "high" | "medium" | "low"
      score_band: "strong" | "moderate" | "weak"
      rationale: [str]
    }
    dominant_drivers: [DriverRef]
    dominant_risks: [RiskRef]
    tradability_state: "good" | "selective" | "poor" | "do_not_deploy"
    volatility_context: {
      regime: str
      path_dependency: "low" | "medium" | "high"
      escape_window_quality: "good" | "limited" | "poor" | "none"
      asymmetry_state: "favorable" | "balanced" | "unfavorable"
    }
    scenario_posture: {
      base_case: str
      adverse_case: str
      favorable_case: str
      invalidation_summary: [str]
    }
  }
  conflict_map: {
    status: "none" | "contained" | "active" | "blocking"
    pairwise_conflicts: [ConflictRecord]
    vetoes: [VetoRecord]
    dampeners: [DampenerRecord]
    unresolved_questions: [str]
  }
  execution_state: {
    deployment_status: "deployable" | "selective" | "standby" | "blocked"
    execution_bias: "long_bias" | "short_bias" | "neutral" | "relative_value" | "optional_only"
    structure_preference: [str]
    sizing_posture: "normal" | "reduced" | "pilot_only" | "none"
    timing_posture: "now" | "wait_for_confirmation" | "event_sensitive" | "do_not_enter"
    risk_directives: [str]
    invalidation_triggers: [str]
    escalation_flags: [str]
  }
  review: {
    human_summary: str
    thesis_trace: [TraceRecord]
    required_manual_checks: [str]
  }
  learning_hooks: {
    snapshot_key: str
    comparison_keys: [str]
    outcome_tags: [str]
    confidence_journal: [ConfidenceNote]
  }
}
```

### Notes on shape

- `domain_outputs` preserves domain ownership. Raw agent conclusions remain visible instead of being flattened.
- `synthesis` is the only layer allowed to speak for the combined thesis.
- `conflict_map` is explicit rather than implied by low confidence.
- `execution_state` is downstream-facing and should be derived, not free-authored by Execution.
- `learning_hooks` exists for auditability and later review, not live mutation.

## 2. Standard Agent Output Contract

Each interpretive agent should emit one standardized envelope with domain-specific payload fields inside a bounded section.

### Standard contract

```text
AgentOutput
{
  agent_name: str
  domain: "macro_regime" | "geopolitical_premium" | "market_quality" | "options_behavior"
  ownership_statement: str
  as_of: datetime
  coverage_state: "complete" | "partial" | "degraded" | "unavailable"
  primary_classification: str
  directional_bias: "bullish" | "bearish" | "neutral" | "mixed" | "non_directional"
  confidence: {
    level: "high" | "medium" | "low"
    numeric: int
    rationale: [str]
  }
  key_drivers: [DriverRecord]
  key_risks: [RiskRecord]
  warnings: [str]
  invalidation_conditions: [str]
  transmission_path: [str]
  review_notes: [str]
  downstream_implications: [str]
  domain_payload: object
}
```

### Required standardized fields

- `agent_name`
- `domain`
- `ownership_statement`
- `as_of`
- `coverage_state`
- `primary_classification`
- `directional_bias`
- `confidence`
- `key_drivers`
- `key_risks`
- `warnings`
- `invalidation_conditions`
- `downstream_implications`
- `domain_payload`

### Optional standardized fields

- `transmission_path`
- `review_notes`

### What varies by agent

`domain_payload` is where domain specificity lives:

- Macro Regime:
  `regime_label`, `growth_inflation_mix`, `liquidity_state`, `policy_pressure`
- Geopolitical Premium:
  `stress_state`, `event_decay_profile`, `transmission_assets`, `tail_risk_state`
- Market Quality:
  `tradability_rating`, `breadth_state`, `liquidity_state`, `fragility_state`
- Options Behavior:
  `vol_regime`, `skew_state`, `term_structure_state`, `convexity_state`, `escape_window_state`, `path_dependency_state`

### Contract rules

- Every agent must declare what it owns and what it does not own.
- Every agent must expose invalidation conditions in plain language.
- Every agent may describe downstream implications, but may not author execution decisions.
- No agent should emit a global score for the whole system.

## 3. Conflict Resolution Model

Conflict resolution should be rule-based, legible, and asymmetric. It should not average opinions together.

### Conflict states

- `aligned`
  Domains materially support the same posture.
- `mixed`
  Domains differ, but disagreement is not severe enough to impair deployment.
- `conflicted`
  Domains disagree in a way that weakens conviction or narrows valid structures.
- `blocked`
  At least one domain creates a no-deployment condition for the current thesis.

### Resolution hierarchy

1. Check coverage quality.
2. Check hard vetoes.
3. Check tradability constraints.
4. Check directional alignment.
5. Check volatility and path constraints.
6. Derive deployment posture.

### Domain-specific conflict behavior

- Macro Regime sets broad directional backdrop.
- Geopolitical Premium can dampen or veto macro expression when event risk dominates.
- Market Quality can block deployment even when directional thesis is attractive.
- Options Behavior can reshape valid structures even when direction is unchanged.

### Veto and dampening model

```text
Veto examples
- market_quality.tradability_rating = do_not_trade -> deployment blocked
- options_behavior.escape_window_state = none and convexity_state = hostile -> block leveraged expression
- geopolitical_premium.tail_risk_state = acute -> block normal sizing into event window
```

```text
Dampener examples
- macro bullish + geo stressed -> keep bias but reduce conviction and sizing
- macro mixed + options favorable -> allow selective structures, not broad deployment
- market quality poor + options favorable -> optional-only posture, delayed timing, reduced size
```

### Confidence reduction rules

Confidence should be shaped, not averaged.

- Reduce confidence when a high-confidence domain materially opposes the base thesis.
- Reduce confidence when market quality is degraded, even if directional alignment exists.
- Reduce confidence when options path dependency is high and escape windows are poor.
- Reduce confidence when one or more agents are partial or degraded.
- Preserve domain confidence separately from thesis conviction so reviewers can see whether the weakness came from disagreement or uncertainty.

### Pairwise conflict record

```text
ConflictRecord
{
  left_domain: str
  right_domain: str
  conflict_type: "directional" | "timing" | "tradability" | "volatility" | "tail_risk"
  severity: "low" | "medium" | "high"
  summary: str
  thesis_effect: str
  resolution: "none" | "dampen" | "narrow" | "block"
}
```

### Design principle

The engine should answer:

- What is the base thesis?
- What is fighting that thesis?
- Does the conflict change direction, timing, sizing, or structure?

If the object cannot answer those questions directly, it is too vague.

## 4. Execution Input Contract

Execution should consume only the thesis-engine output needed to act, plus traceable references back to domain rationale. It should not reinterpret raw domain signals.

### Proposed execution contract

```text
ExecutionInput
{
  thesis_id: str
  as_of: datetime
  deployment_status: "deployable" | "selective" | "standby" | "blocked"
  execution_bias: "long_bias" | "short_bias" | "neutral" | "relative_value" | "optional_only"
  conviction_level: "high" | "medium" | "low"
  tradability_state: "good" | "selective" | "poor" | "do_not_deploy"
  timing_posture: "now" | "wait_for_confirmation" | "event_sensitive" | "do_not_enter"
  structure_preference: [str]
  sizing_posture: "normal" | "reduced" | "pilot_only" | "none"
  dominant_drivers: [DriverRef]
  dominant_risks: [RiskRef]
  risk_directives: [str]
  invalidation_triggers: [str]
  escalation_flags: [str]
  rationale_trace_ids: [str]
}
```

### Upstream responsibility

The thesis engine is responsible for:

- combining domain conclusions
- exposing conflicts clearly
- converting conflict into posture, sizing, and timing constraints
- preserving enough rationale for human review

### Downstream responsibility

Execution is responsible for:

- selecting expressions consistent with the provided posture
- enforcing operator and portfolio constraints
- mapping posture into trade candidates
- refusing to exceed thesis constraints

### What Execution should not see as a decision input

- raw normalized feature data
- agent-private intermediate reasoning
- hidden fallback heuristics
- separate domain outputs treated as invitations to reinterpret the thesis

Execution may still access domain summaries for traceability, but not for independent thesis formation.

## 5. Learning / Logging Hooks

Learning should attach to the thesis state at durable checkpoints.

### Attachment points

- Pre-execution thesis snapshot
- Execution decision snapshot
- Post-trade or post-window outcome snapshot
- Retrospective review snapshot

### Required logged artifacts

```text
LearningAttachment
{
  thesis_id: str
  snapshot_type: "pre_execution" | "execution" | "outcome" | "retrospective"
  timestamp: datetime
  thesis_state_summary: str
  domain_confidence_map: { domain: confidence_level }
  conflict_status: str
  deployment_status: str
  expected_path: str
  realized_path: str | null
  review_notes: [str]
  operator_overrides: [str]
}
```

### Confidence tracking hooks

- Store original thesis conviction at decision time.
- Store any manual override to posture or sizing.
- Store whether the realized path matched the dominant-driver thesis.
- Store whether failure came from bad direction, bad timing, poor tradability, or nonlinear path error.

### Guardrail

Learning may generate suggestions, diagnostics, and review prompts, but it must not automatically alter thesis-engine logic or domain thresholds.

## 6. Suggested Module Layout

This phase should remain specification-first.

### Proposed layout

```text
signal-forge/
└── docs/
    ├── UNIFIED_THESIS_ENGINE.md
    ├── THESIS_STATE_SCHEMA.md
    ├── EXECUTION_INTERFACE.md
    └── LEARNING_ATTACHMENTS.md
```

### Later implementation-oriented layout

```text
signal-forge/
└── thesis/
    ├── contracts.py
    ├── engine.py
    ├── conflict_rules.py
    ├── execution_view.py
    ├── review_trace.py
    └── types.py
```

### Module responsibilities

- `contracts.py`
  Shared interfaces for `AgentOutput`, `UnifiedThesisState`, and `ExecutionInput`
- `engine.py`
  Aggregation and synthesis orchestration
- `conflict_rules.py`
  Explicit conflict, veto, and dampening policies
- `execution_view.py`
  Reduced view consumed by Execution
- `review_trace.py`
  Human-readable trace assembly
- `types.py`
  enums, typed dictionaries, and schema primitives

## 7. Top 5 Risks

1. Hidden score blending
   Pressure to summarize the system into one number will destroy domain legibility and mask conflict.

2. Execution reinterpreting upstream logic
   If Execution starts reading raw domain outputs directly, the thesis engine stops being the system contract.

3. Ambiguous ownership between Geo, Market Quality, and Options
   Without explicit boundaries, event risk, tradability, and nonlinear structure can overlap and create duplicated interpretation.

4. Overloaded schema
   If the thesis object tries to carry every intermediate detail, it will become hard to review and harder to implement correctly.

5. Confidence misuse
   If confidence is treated as certainty rather than shaped conviction under constraints, the system will hide path risk and thesis fragility.

## 8. Manual Review Checklist Before Implementation

- Can a reviewer identify the base thesis in under one minute?
- Can a reviewer see which domain owns each major claim?
- Can a reviewer distinguish disagreement from low data quality?
- Can a reviewer tell whether a conflict changes direction, timing, sizing, or structure?
- Can a reviewer see why a thesis is deployable, selective, or blocked?
- Are options-specific path dependency and escape windows still explicit?
- Is Execution prevented from reforming its own thesis from raw domain outputs?
- Are learning hooks audit-friendly and clearly separated from live decision logic?
- Does the schema avoid a master blended score?
- Is there a single place where veto and dampening rules will live later?
