# DEV LOG

- Workflow initialized.
- 2026-04-01: Completed NEXT_STEPS Phase 1 only by adding the `DislocatonReading`
  contract and a `DislocationFetcher` stub that returns hardcoded futures/ETF percent
  moves following the existing stub pattern. No Phase 2+ engine, tests, pipeline, or
  report wiring were touched.
- 2026-04-01: Completed NEXT_STEPS Phase 2 only by adding a pure
  `DislocationEngine` module that classifies divergence between futures and ETF
  percent moves into `CLEAN`, `MIXED`, and `DISLOCATION` using simple hardcoded
  thresholds: under `1.0`, `1.0` through `3.0`, and above `3.0`. Added unit tests
  for all three cases. Pipeline and report/output wiring were not changed.
- 2026-04-01: PRD upgraded: interpretation-aware dislocation engine.
- 2026-04-01: contracts fixed: correct dislocation model
- 2026-04-01: engine upgraded: leader/lagger awareness
- 2026-04-01: pipeline integrated: dislocation engine
- 2026-04-01: report output added for dislocation signal
- 2026-04-01: standards added: naming, formatting, and signal schema
- 2026-04-01: standardized dislocation output: schema, formatting, and console template
- 2026-04-03: added a dedicated safeguards layer with JSONL logging, strict expression/volatility/catalyst rails, validated override codes, and pipeline wiring.
- 2026-04-03: added a V1 pure-Python backtest engine that simulates credit/debit proxy trades on the underlying and reports win rate, expectancy, drawdown, profit factor, and no-trade frequency.
- 2026-04-03: scaled up the Morning Macro Edge dashboard for better desktop readability, added a `_site/` static-site builder with a lightweight landing page, and added a GitHub Pages Actions workflow plus local preview notes.
