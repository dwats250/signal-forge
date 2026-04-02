# Dislocation Engine PRD

## Goal
Detect and classify macro dislocations between futures and corresponding ETFs to surface actionable trading signals.

## Context
Markets often diverge during headline-driven or macro events (e.g., oil vs energy equities, metals vs miners).

These divergences can signal:
- delayed equity response (catch-up potential)
- false moves in underlying commodities
- structural inefficiencies during volatility

The system aims to systematically detect and interpret these dislocations.

## Requirements

### Core Logic
- Compare percentage change between futures and corresponding ETF
- Compute divergence internally (do NOT pass divergence as input)
- Classify the relationship into:
  - CLEAN
  - MIXED
  - DISLOCATION

### Classification Rules (Initial Version)

CLEAN:
- Futures and ETF move in the same direction
- Low divergence

MIXED:
- Futures and ETF move in the same direction
- Moderate divergence

DISLOCATION:
- Futures and ETF move in opposite directions OR
- Divergence exceeds threshold (> 3%)

### Output
Return:
- signal classification (CLEAN / MIXED / DISLOCATION)
- computed divergence
- explanation string (why classification occurred)

## Constraints
- Pure function (no I/O)
- Deterministic and testable
- No external data (stub-only for now)
- Signal must NOT be stored in DislocationReading

## Deliverables
- dislocation_engine.py module
- classify_dislocation(reading) function
- unit tests (aligned, mixed, opposite direction)
- integration-ready output

## Signal Interpretation

The system must interpret—not just detect—dislocation:

- Futures move strongly while ETF lags  
  → potential equity lag / catch-up opportunity

- ETF moves without futures  
  → potential false move / overextension

- Both align  
  → healthy trend (CLEAN)

The output must include a brief explanation string.

## Acceptance Criteria
- Correctly classifies:
  - aligned move (CLEAN)
  - moderate divergence (MIXED)
  - opposite direction (DISLOCATION)
- Explanation string reflects reasoning
- Fully testable with stub inputs
