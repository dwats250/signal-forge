# DEV LOG

- Workflow initialized.
- 2026-04-07: archived DuckDNS out of active automation, moved Morning Edge report generation to 6:00 AM weekdays, kept live observation at 6:30 AM, and hardened gold rendering so invalid values fall back to unavailable instead of polluting the report.
- 2026-04-05: tightened report operations by adding US market holiday-aware premarket scheduling, portable `latest_*` output pointers, and docs that prefer cron/systemd one-shot scheduling over a Python daemon loop.
- 2026-04-05: added safe report lifecycle helpers plus thin Sunday/Daily scheduling wrappers so live report outputs promote atomically, prior successful HTML/PDF artifacts rotate into dated archives, and manual CLI entrypoints stay intact.
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
- 2026-04-04: backtest engine annotated as NOT ACTIVE. Reserved for post-v1 validation. Will integrate only after live signals are stable, Trade Policy Layer is complete, and 20–30 real trades are logged.
- 2026-04-03: scaled up the Morning Macro Edge dashboard for better desktop readability, added a `_site/` static-site builder with a lightweight landing page, and added a GitHub Pages Actions workflow plus local preview notes.
- 2026-04-03: added the Morning Macro Edge architecture and UX reference PRD at `docs/PRDs/macro_morning_edge_architecture_ux_v1.md` to lock page flow, hierarchy, deferred-data placeholders, and implementation constraints for future UI passes.
