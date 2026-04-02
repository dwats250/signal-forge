# Roadmap

## 1. Core Engine

Goal:
Establish the core signal engine and the minimum decision-support path.

What is complete:
- core contracts for domain outputs, theses, conflicts, execution inputs, logs, and dislocation readings
- deterministic dislocation classification
- thesis construction across domain outputs
- conflict evaluation and execution gating
- audit logging
- initial unit and integration tests

What is missing:
- deeper signal coverage beyond the current dislocation path
- stronger boundaries between pipeline stages
- production-grade ingestion and validation workflows

## 2. Pipeline Standardization

Goal:
Align the implementation to the canonical pipeline and make subsystem boundaries explicit.

What is complete:
- a working end-to-end flow exists
- core modules already map to ingestion, normalization, classification, logging, and execution gating

What is missing:
- a formal scoring layer
- a formal context-filtering layer
- clearer handoff boundaries between reading construction, classification, and output
- consistent documentation across the repository

## 3. Output + Usability

Goal:
Make signals easier to inspect, compare, and act on.

What is complete:
- structured pipeline return payloads
- compact console output for dislocation summaries
- JSONL audit logging

What is missing:
- report generation aligned to operator workflows
- dashboard-ready output structures
- cleaner top-level summaries for rapid review

## 4. Validation + Replay

Goal:
Move from basic correctness checks to systematic review and replay.

What is complete:
- baseline unit coverage for the dislocation engine
- integration coverage for core pipeline behavior

What is missing:
- replay tooling
- benchmark scenarios
- historical validation datasets
- regression suites tied to signal quality

## 5. Expansion + Automation

Goal:
Increase system breadth without reducing explainability.

What is complete:
- the current architecture supports additional signal modules and downstream output layers

What is missing:
- more input coverage
- additional classification modules
- automated report and dashboard production
- stronger operational tooling around review and monitoring
