# Codex Output

Files created:
- `signal_forge/backtest/trades.py`
- `signal_forge/backtest/metrics.py`
- `signal_forge/data/__init__.py`
- `signal_forge/data/loader.py`
- `signal_forge/safeguards/__init__.py`
- `signal_forge/safeguards/guardrails.py`
- `docs/superpowers/plans/2026-04-03-phase1-safeguards-backtest.md`

Files modified:
- `signal_forge/config.py`
- `signal_forge/backtest/engine.py`
- `signal_forge/rails/safeguards.py`
- `signal_forge/__main__.py`

Functions implemented:
- `signal_forge.safeguards.guardrails.validate_trade(trade, market_context) -> dict`
- `signal_forge.backtest.engine.run_backtest(trades, price_data, log_path=None, notes="phase1 baseline") -> dict`
- `signal_forge.backtest.metrics.calculate_metrics(trade_results) -> dict`
- `signal_forge.data.loader.load_price_series(symbol: str) -> list[float]`
- CLI demo path: `python -m signal_forge backtest-demo`

How to run backtest:
```python
from signal_forge.backtest import Trade, run_backtest

trades = [
    Trade("SPY", "bullish", "call_debit", 100.0, 98.0, 104.0),
    Trade("QQQ", "bearish", "call_credit", 100.0, 102.0, 96.0),
]
data = {
    "SPY": [100.0, 101.0, 104.5],
    "QQQ": [100.0, 99.5, 99.2, 99.0, 98.8],
}
results = run_backtest(trades, data)
print(results)
```

Assumptions made:
- Phase 1 uses underlying price movement as the trade proxy rather than option pricing.
- FMP access is optional and only attempted when `FMP_API_KEY` is set.
- Existing `SafeguardsLayer` and `SimpleBacktestEngine` imports remain available as compatibility wrappers.

Known limitations:
- No options chain, Greeks, or IV surface modeling.
- Timeout exits use last observed underlying price and convert the move into a simple R multiple.
- FMP fetch is intentionally lightweight and falls back to deterministic mock data when unavailable.
