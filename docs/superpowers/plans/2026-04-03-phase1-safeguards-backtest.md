# Phase 1 Safeguards and Backtesting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal safeguards layer and lightweight backtesting engine that validate trade quality, simulate simple outcomes, and write baseline logs.

**Architecture:** Add small package modules under `signal_forge` for safeguards, trades, metrics, config, and data loading. Keep the current repository import surface stable by routing existing classes through the new Phase 1 primitives instead of replacing the repo structure wholesale.

**Tech Stack:** Python 3.11+, standard library dataclasses/pathlib/json/urllib, unittest

---

### Task 1: Define the Phase 1 data model and defaults

**Files:**
- Create: `signal_forge/config/__init__.py`
- Create: `signal_forge/config/defaults.py`
- Create: `signal_forge/backtest/trades.py`
- Modify: `signal_forge/backtest/__init__.py`
- Test: `tests/test_backtest_engine.py`

- [ ] Add minimal configuration constants for risk/reward, timeout bars, volatility mapping, and default log path.
- [ ] Add a `Trade` dataclass with the Phase 1 fields and a timestamp default.
- [ ] Export the new `Trade` type from `signal_forge.backtest`.
- [ ] Keep the shapes small and serializable so later logging and metrics code can consume them directly.

### Task 2: Implement safeguard validation primitives and compatibility wrapper

**Files:**
- Create: `signal_forge/safeguards/__init__.py`
- Create: `signal_forge/safeguards/guardrails.py`
- Modify: `signal_forge/rails/safeguards.py`
- Test: `tests/test_safeguards.py`

- [ ] Implement `validate_trade(trade, market_context) -> dict` with checks for risk/reward, directional structure alignment, volatility fit, and market quality gating.
- [ ] Return the exact Phase 1 payload keys: `approved`, `score`, and `reasons`.
- [ ] Keep `SafeguardsLayer` available by delegating to the new validation function and preserving JSONL logging behavior.
- [ ] Cover `CHAOTIC`, `MIXED`, and aligned high-quality trade cases in tests.

### Task 3: Implement the lightweight backtesting engine and metrics

**Files:**
- Modify: `signal_forge/backtest/engine.py`
- Create: `signal_forge/backtest/metrics.py`
- Test: `tests/test_backtest_engine.py`

- [ ] Implement `run_backtest(trades, price_data) -> dict` that simulates stop, target, and timeout outcomes per trade.
- [ ] Record outcome, approximate pnl, duration, and result metadata for each trade.
- [ ] Compute win rate, average R multiple, simple max drawdown, and total return in a dedicated metrics function.
- [ ] Preserve the existing `SimpleBacktestEngine` entry point by adapting it to the new engine.

### Task 4: Add data loading and run logging

**Files:**
- Create: `signal_forge/data/__init__.py`
- Create: `signal_forge/data/loader.py`
- Modify: `signal_forge/backtest/engine.py`
- Test: `tests/test_backtest_engine.py`

- [ ] Implement `load_price_series(symbol)` with optional FMP fetch when `FMP_API_KEY` is available and deterministic mock fallback otherwise.
- [ ] Append a JSONL run summary to `logs/backtest_log.jsonl` on each backtest.
- [ ] Keep network use optional so tests remain fully local.

### Task 5: Wire example usage and operator docs

**Files:**
- Modify: `signal_forge/__main__.py`
- Modify: `docs/agent_loop/codex_out.md`
- Optional context: `README.md`
- Test: `tests/test_signal_forge_cli.py`

- [ ] Add a simple CLI example path to run the Phase 1 backtest demo without introducing UI or heavy plumbing.
- [ ] Document files created, implemented functions, run instructions, assumptions, and known limitations in `docs/agent_loop/codex_out.md`.
- [ ] Ensure the CLI example and docs show the required `trades = [Trade(...), Trade(...)]` pattern.
