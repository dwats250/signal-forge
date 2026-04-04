# Signal Forge

## What Signal Forge Is

Signal Forge is a dislocation detection and classification engine for trading decision support.

It converts macro and price relationships into structured, explainable signals that can be reviewed, validated, and acted on with clear context.

## Why It Exists

Market moves often break alignment across futures, ETFs, options behavior, and macro posture.

Signal Forge exists to:

- detect those breaks early
- classify them in a consistent way
- preserve the reasoning behind each signal
- support faster, more disciplined trading decisions

## Core Pipeline

Signal Forge follows one canonical pipeline:

Inputs
-> Normalization
-> Reading Construction
-> Classification
-> Scoring
-> Context Filters
-> Output
-> Logging / Validation

Current implementation covers the early pipeline directly and provides initial logging and validation support.

The current execution path now also includes a safeguards layer that blocks invalid trade expression and a simple underlying-based backtest layer that validates the decision logic before more advanced options modeling is introduced.

## Current System Status

Signal Forge is in active core-engine development.

Implemented now:

- stubbed input ingestion for domain signals and dislocation pairs
- normalized contracts for agent outputs, theses, conflicts, execution inputs, and dislocation readings
- deterministic dislocation classification
- thesis construction across macro, geopolitical, market quality, and options domains
- conflict evaluation, expression guardrails, and execution gating
- simple underlying-based proxy backtesting for credit and debit expressions
- audit logging and initial test coverage

Not complete yet:

- scoring as a dedicated subsystem
- context filters as a formal post-classification layer
- polished output surfaces for dashboards and reports
- replay, validation, and benchmark tooling beyond current unit and integration tests

## Roadmap Summary

1. Core Engine
Core contracts, classification, thesis construction, conflict handling, and logging are in place.

2. Pipeline Standardization
The immediate focus is aligning every component to the canonical pipeline and tightening subsystem boundaries.

3. Output + Usability
Next work centers on structured reports, dashboards, and operator-facing output.

4. Validation + Replay
The system then needs replay tools, validation datasets, and review workflows.

5. Expansion + Automation
Later work extends coverage, increases automation, and broadens the signal set without weakening explainability.

## Static Site Preview

Morning Edge architecture and UX reference:

- `docs/PRDs/macro_morning_edge_architecture_ux_v1.md`

Build the publishable static site:

```bash
python3 -m reports.build_all
```

Preview it locally:

```bash
cd _site && python3 -m http.server 8000
```

Then open `http://localhost:8000`.
