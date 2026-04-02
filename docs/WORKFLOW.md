# Workflow

## Build Loop

Thesis -> Codex -> Review -> Claude -> Test -> Log

## Stage Definitions

- Thesis: Define the change, scope, and expected behavioral impact.
- Codex: Produce architecture, planning, review, and documentation guidance.
- Review: Confirm correctness, boundaries, and phase readiness before implementation.
- Claude: Implement the approved scoped change only.
- Test: Validate intended behavior and check for regressions.
- Log: Record decisions, results, and deferred items.

## Branch Workflow

- Create a focused branch for each approved phase or scoped change.
- Keep branch scope aligned to one decision set at a time.
- Merge only after review and validation are complete.

## Iteration Model

- Work in small, reviewable phases.
- Freeze scope before implementation starts.
- Capture deferred work explicitly instead of expanding the active phase.

## Validation Steps

- Confirm scope against the active phase document.
- Review architecture and ownership boundaries before coding.
- Validate implementation against intended behavior.
- Verify tests and review artifacts before logging completion.
