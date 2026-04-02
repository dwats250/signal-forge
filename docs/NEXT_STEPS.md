# NEXT STEPS

## Dislocation Engine — Phased Plan

---

### Phase 1: Data Layer

Define the dislocation data contract and a price-fetch stub.

- Add `DislocatonReading` dataclass to `contracts.py`:
  - Fields: `futures_symbol`, `etf_symbol`, `futures_pct_change`, `etf_pct_change`, `divergence`, `signal` (CLEAN / MIXED / DISLOCATION)
- Add `DislocationFetcher` stub in `signal_forge/agents/` that accepts a symbol pair and returns hardcoded % changes (mirrors the `StubAgent` pattern)
- No live data yet — just the shape

---

### Phase 2: Dislocation Engine Module

Build `signal_forge/dislocation_engine.py`.

- `DislocationEngine.evaluate(futures_pct: float, etf_pct: float) -> DislocatonReading`
- Divergence = `abs(futures_pct - etf_pct)`
- Threshold config (start with hardcoded defaults):
  - `< 1.5%` → CLEAN
  - `1.5–3%` → MIXED
  - `>= 3%` → DISLOCATION
- Unit-testable with no I/O dependencies

---

### Phase 3: Tests

Add `tests/test_dislocation_engine.py`.

- Test all three signal bands (CLEAN, MIXED, DISLOCATION)
- Test the canonical acceptance criterion: oil vs XLE divergence produces the correct signal
- Test boundary values at thresholds

---

### Phase 4: Macro Pulse Integration

Wire the engine into the existing pipeline.

- Add `dislocation` as a new domain in `SignalForgePipeline.run()` alongside macro, geo, market_quality, options
- Feed `DislocatonReading.signal` into `AgentOutput.special_flags` (key: `"dislocation"`) on the `MacroAgent` output, or introduce it as its own agent
- Ensure `ConflictRulesEngine` and `ThesisEngine` are not broken by the addition (no conflict rule changes required in this phase)

---

### Phase 5: Report Output

Make the signal visible.

- Emit `dislocation_signal` in the top-level dict returned by `SignalForgePipeline.run()`
- Add a formatted line to any existing report/print output so the signal appears in the console run (e.g., `[DISLOCATION] CL vs XLE: +4.2% divergence`)

---

### Acceptance Gate

Before closing the feature:
- [ ] Oil (CL) vs XLE divergence detected correctly end-to-end
- [ ] Signal (CLEAN / MIXED / DISLOCATION) visible in pipeline output
- [ ] All existing tests still pass
