# Architecture

## System Philosophy

- Signal over noise
- Structure over intuition
- Explainability over black-box output

## Canonical Pipeline

This is the single source of truth for how Signal Forge should be described:

Inputs
-> Normalization
-> Reading Construction
-> Classification
-> Scoring
-> Context Filters
-> Output
-> Logging / Validation

## Pipeline Definition

### Inputs

Raw market, macro, geopolitical, options, and pair-move data enter the system.

### Normalization

Inputs are converted into stable, comparable shapes with explicit field definitions and predictable units.

### Reading Construction

Normalized inputs become typed readings and domain outputs that can move through the pipeline without hidden assumptions.

### Classification

The engine turns readings into explicit labels, directional relationships, and explanations.

### Scoring

Classification results are ranked by strength, quality, and actionability.

This layer is planned, not complete.

### Context Filters

Signals are filtered by regime, conflict state, timing, and execution constraints before they are surfaced.

This layer exists in partial form through current conflict handling, but it is not yet standardized as its own subsystem.

### Output

Structured signals are rendered into operator-facing formats such as console summaries, reports, and dashboards.

Current output is functional but minimal.

### Logging / Validation

Every decision path should be reviewable through logs, tests, and later replay and validation workflows.

Logging exists now. Validation exists in early form through unit and integration tests.

## Subsystems

### Ingestion

Purpose:
Collect raw input states for domain agents and dislocation pairs.

Inputs:
- runtime context
- symbol pairs
- stubbed market move values

Outputs:
- domain input payloads for agent stubs
- raw pair move data for futures and ETFs

Current implementation:
`signal_forge.agents.stubs` provides stub agents and a `DislocationFetcher`.

### Normalization

Purpose:
Convert raw values into typed, consistent internal structures.

Inputs:
- raw domain state overrides
- futures and ETF percentage moves

Outputs:
- `AgentOutput`
- `DislocationReading`
- shared contract objects used by downstream stages

Current implementation:
`signal_forge.contracts` defines the core normalized contracts.

### Reading Construction

Purpose:
Build the internal readings and domain summaries that classification depends on.

Inputs:
- normalized market and domain values

Outputs:
- dislocation readings
- domain outputs
- thesis inputs

Current implementation:
`SignalForgePipeline` assembles domain outputs and dislocation readings before classification and thesis construction.

### Classification

Purpose:
Turn readings into explainable labels and thesis states.

Inputs:
- `DislocationReading`
- domain `AgentOutput` values

Outputs:
- `DislocationClassification`
- `Thesis`
- `ConflictResult`

Current implementation:
- `signal_forge.dislocation_engine`
- `signal_forge.thesis_engine`
- `signal_forge.conflict_rules`

### Scoring

Purpose:
Rank signals by quality, urgency, and trade suitability.

Inputs:
- classified signals
- thesis state
- contextual constraints

Outputs:
- scored signals
- sortable priority values

Current implementation:
Not implemented.

### Context Filtering

Purpose:
Apply post-classification constraints before a signal becomes actionable.

Inputs:
- thesis state
- conflict states
- event and volatility flags

Outputs:
- deployment constraints
- filtered execution posture

Current implementation:
Partial. `ConflictRulesEngine` already applies blockers and constraints, but the broader context-filtering layer is not separated yet.

### Output

Purpose:
Present signals in structured forms for operators and downstream systems.

Inputs:
- dislocation classifications
- thesis state
- conflict results
- execution inputs

Outputs:
- pipeline return payload
- console output
- future report and dashboard artifacts

Current implementation:
`SignalForgePipeline.run()` returns a structured payload and prints a compact dislocation summary.

### Logging

Purpose:
Persist decisions and their supporting context for audit and review.

Inputs:
- execution input
- decision label
- conflict notes

Outputs:
- JSONL audit entries

Current implementation:
`signal_forge.audit.AuditLogger`

### Validation

Purpose:
Verify correctness, stability, and replayability.

Inputs:
- pipeline behavior
- classification rules
- expected outputs

Outputs:
- unit tests
- integration tests
- future replay and benchmark results

Current implementation:
Early. Current coverage lives in `tests/test_dislocation_engine.py` and `tests/test_pipeline.py`.
