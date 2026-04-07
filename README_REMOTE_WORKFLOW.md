# Signal Forge

Use this repo as the single source of truth.

## Live Pipeline Ops Note

`python3 run_live_pipeline.py` does not use Anthropic or Claude credentials in its fetch path. The live command flows through `run_live_pipeline.py -> signal_forge.data.live_fetch.collect_market_snapshot() -> fmp/stooq providers -> SignalForgePipeline`.

If your terminal shows `Auth conflict: Both a token (claude.ai) and an API key (ANTHROPIC_API_KEY) are set`, treat that as a Claude Code tooling warning unless you are separately running report generation that calls `reports/morning_edge.py` or `python3 -m reports.build_all`.

Safe operator checks:

```bash
python3 run_live_pipeline.py --preflight
python3 run_live_pipeline.py
SIGNAL_FORGE_DEBUG_FETCH=1 python3 run_live_pipeline.py --preflight
```

Local auth setup for `fmp`:

```bash
cat > .env <<'EOF'
FMP_API_KEY=your_real_fmp_key_here
EOF
```

Behavior policy:

- Critical live dataset for this command: equity breadth (`SPY`, `QQQ`, `IWM`) with at least 2 symbols present, plus `VIX`.
- Optional/degraded groups: `DXY`, `US10Y`, `GOLD`, `OIL`, `XLE`.
- Optional failures no longer hard-skip the entire run. They log as degraded and the pipeline proceeds.
- Full skip now means the minimum viable dataset is unavailable, not just that one optional provider call failed.
