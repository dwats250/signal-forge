## Goal
Detect macro dislocations between futures and ETFs

## Context
Markets diverge during headline events (oil vs equities, metals vs miners)

## Requirements
- Compare futures vs ETF % change
- Flag divergence thresholds
- Output signal: CLEAN / MIXED / DISLOCATION

## Deliverables
- Python module
- Integration into Macro Pulse

## Acceptance Criteria
- Detect oil vs XLE divergence correctly
- Output visible signal in report
