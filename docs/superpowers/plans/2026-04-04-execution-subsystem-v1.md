# Execution Subsystem V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a bounded execution subsystem under `signal_forge/execution/` that validates candidates, computes risk, enforces review-before-next-trade, writes logs, and exposes a CLI workflow.

**Architecture:** Replace the legacy single-file `signal_forge/execution.py` module with a package that preserves the `signal_forge.execution` import path. Keep mutation centralized in a single orchestrator, keep gates pure, store append-only operational logs as JSONL, and model the workflow with small dataclasses plus enums.

**Tech Stack:** Python 3.11+, standard library dataclasses/enum/json/pathlib/datetime, unittest

---

### Task 1: Replace the legacy execution module with package boundaries

**Files:**
- Delete: `signal_forge/execution.py`
- Create: `signal_forge/execution/__init__.py`
- Create: `signal_forge/execution/models/__init__.py`
- Create: `signal_forge/execution/gates/__init__.py`
- Create: `signal_forge/execution/policy/__init__.py`
- Create: `signal_forge/execution/review/__init__.py`
- Create: `signal_forge/execution/cli/__init__.py`
- Create: `signal_forge/execution/logs/.gitkeep`
- Test: `tests/test_execution_subsystem.py`

- [ ] Add the new package directories and `__init__.py` exports so `from signal_forge.execution import ExecutionInterface` continues to work for the existing pipeline.
- [ ] Keep the legacy `ExecutionInterface` logic available from the new package to avoid unrelated pipeline regressions while introducing the new orchestrator APIs alongside it.
- [ ] Add a `logs` directory placeholder so append-only execution artifacts have a stable home inside the package tree.

### Task 2: Define execution models and fail-fast validation

**Files:**
- Create: `signal_forge/execution/models/core.py`
- Modify: `signal_forge/execution/models/__init__.py`
- Test: `tests/test_execution_subsystem.py`

- [ ] Add `TradeState`, `StrategyType`, `TradeDirection`, `ReviewDeviationType`, and decision enums that encode the state machine and structured outputs from the PRD.
- [ ] Add dataclasses for `EntryTrigger`, `TradeCandidate`, `TradeTicket`, `ReviewResult`, `PolicyChange`, and `TradeRecord`.
- [ ] Validate invalid stop/entry/target relationships, reject unsupported option structures, and forbid free-text logic fields by keeping entry metadata structured.
- [ ] Include serialization helpers so orchestrator logging can emit JSONL rows without custom encoders.

### Task 3: Implement pure market, setup, and risk gates

**Files:**
- Create: `signal_forge/execution/gates/market.py`
- Create: `signal_forge/execution/gates/setup.py`
- Create: `signal_forge/execution/gates/risk.py`
- Modify: `signal_forge/execution/gates/__init__.py`
- Test: `tests/test_execution_subsystem.py`

- [ ] Implement a market gate that consumes external regime approval only and returns pass/fail metadata without mutating trade state.
- [ ] Implement a setup gate that consumes external conflict-engine output plus the candidate and returns valid/invalid metadata.
- [ ] Implement a risk gate that computes position size strictly from account size, configured risk percent, and stop distance or option max-loss math.
- [ ] Enforce option policy: allow only debit spreads and cash-secured puts, require minimum DTE 21, minimum OI, and maximum spread percentage thresholds.

### Task 4: Add orchestrator, logging, review enforcement, and stale-trade handling

**Files:**
- Create: `signal_forge/execution/orchestrator.py`
- Create: `signal_forge/execution/review/engine.py`
- Create: `signal_forge/execution/policy/store.py`
- Test: `tests/test_execution_subsystem.py`

- [ ] Centralize every state transition inside `ExecutionOrchestrator`.
- [ ] Append trade lifecycle entries to execution JSONL logs and keep closed trades blocked from further progress until a `ReviewResult` is recorded.
- [ ] Reject new tickets when any closed trade lacks a review result.
- [ ] Handle missing market data, partial fills, stale ready trades, and invalid lifecycle transitions with explicit failures.
- [ ] Keep policy changes append-only in `logs/policy_changes.jsonl` and enforce that only one active change exists at a time.

### Task 5: Expose CLI workflow and cover the required tests

**Files:**
- Modify: `signal_forge/__main__.py`
- Create: `signal_forge/execution/cli/submit_trade.py`
- Test: `tests/test_execution_subsystem.py`
- Test: `tests/test_signal_forge_cli.py`

- [ ] Add a CLI subcommand to submit a structured trade candidate from JSON stdin or a file path.
- [ ] Add a CLI subcommand to record a review result for a closed trade.
- [ ] Keep the CLI output JSON-only so it stays scriptable.
- [ ] Cover valid flow, rejected trade, risk calculation, debit spread versus CSP risk, review-before-next-trade enforcement, and invalid input rejection.
