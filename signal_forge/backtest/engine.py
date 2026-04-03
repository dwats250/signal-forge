from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from signal_forge.contracts import (
    BacktestResult,
    BacktestSummary,
    BacktestTradeResult,
    TradeProxy,
)
from signal_forge.backtest.metrics import calculate_metrics
from signal_forge.backtest.trades import Trade
from signal_forge.config import DEFAULT_BACKTEST_LOG_PATH


def run_backtest(
    trades: list[Trade],
    price_data: dict[str, list[float]],
    log_path: Path | None = None,
    notes: str = "phase1 baseline",
) -> dict[str, object]:
    trade_results: list[dict[str, object]] = []
    for trade in trades:
        series = price_data.get(trade.symbol, [])
        trade_results.append(_simulate_trade(trade, series))

    metrics = calculate_metrics(trade_results)
    result = {
        "trades": trade_results,
        "metrics": metrics,
    }
    _append_log(result, log_path or DEFAULT_BACKTEST_LOG_PATH, notes)
    return result


def _simulate_trade(trade: Trade, series: list[float]) -> dict[str, object]:
    if not series:
        return {
            "symbol": trade.symbol,
            "direction": trade.direction,
            "structure": trade.structure,
            "outcome": "no_data",
            "pnl": 0.0,
            "r_multiple": 0.0,
            "duration": 0,
            "exit_price": trade.entry_price,
        }

    future_path = series[1:] if series and series[0] == trade.entry_price else series
    if not future_path:
        future_path = [trade.entry_price]

    stop_index = None
    target_index = None
    for index, price in enumerate(future_path[: trade.timeout_bars], start=1):
        if trade.direction == "bullish":
            if target_index is None and price >= trade.target:
                target_index = index
            if stop_index is None and price <= trade.stop:
                stop_index = index
        else:
            if target_index is None and price <= trade.target:
                target_index = index
            if stop_index is None and price >= trade.stop:
                stop_index = index
        if target_index is not None or stop_index is not None:
            break

    if target_index is not None and (stop_index is None or target_index <= stop_index):
        r_multiple = round(trade.risk_reward_ratio, 4)
        return {
            "symbol": trade.symbol,
            "direction": trade.direction,
            "structure": trade.structure,
            "outcome": "win",
            "pnl": r_multiple,
            "r_multiple": r_multiple,
            "duration": target_index,
            "exit_price": trade.target,
        }

    if stop_index is not None:
        return {
            "symbol": trade.symbol,
            "direction": trade.direction,
            "structure": trade.structure,
            "outcome": "loss",
            "pnl": -1.0,
            "r_multiple": -1.0,
            "duration": stop_index,
            "exit_price": trade.stop,
        }

    exit_price = future_path[min(len(future_path), trade.timeout_bars) - 1]
    risk = trade.risk or 1.0
    if trade.direction == "bullish":
        raw_r = (exit_price - trade.entry_price) / risk
    else:
        raw_r = (trade.entry_price - exit_price) / risk
    r_multiple = round(raw_r, 4)
    return {
        "symbol": trade.symbol,
        "direction": trade.direction,
        "structure": trade.structure,
        "outcome": "timeout",
        "pnl": r_multiple,
        "r_multiple": r_multiple,
        "duration": min(len(future_path), trade.timeout_bars),
        "exit_price": exit_price,
    }


def _append_log(result: dict[str, object], log_path: Path, notes: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    metrics = result["metrics"]
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trades_tested": len(result["trades"]),
        "win_rate": metrics["win_rate"],
        "avg_r": metrics["average_r_multiple"],
        "notes": notes,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True))
        handle.write("\n")


class SimpleBacktestEngine:
    def run(
        self,
        prices: list[float],
        expression_type: str,
        allowed: bool,
        confidence_score: int,
        time_window: int = 5,
    ) -> BacktestResult:
        if not prices:
            raise ValueError("prices must not be empty")

        proxy = self._build_proxy(prices[0], expression_type, time_window)
        trade = self._simulate_legacy_trade(
            prices,
            expression_type,
            allowed,
            confidence_score,
            proxy,
        )
        summary = self._summarize_legacy([trade])
        return BacktestResult(summary=summary, trades=[trade])

    def _build_proxy(self, entry_price: float, expression_type: str, time_window: int) -> TradeProxy:
        if expression_type == "CREDIT_BULL":
            stop_level = entry_price * 0.98
            target_level = entry_price * 1.01
            max_loss = -2.0
            max_gain = 1.0
        elif expression_type == "CREDIT_BEAR":
            stop_level = entry_price * 1.02
            target_level = entry_price * 0.99
            max_loss = -2.0
            max_gain = 1.0
        elif expression_type == "DEBIT_BULL":
            stop_level = entry_price * 0.98
            target_level = entry_price * 1.03
            max_loss = -1.0
            max_gain = 2.0
        else:
            stop_level = entry_price * 1.02
            target_level = entry_price * 0.97
            max_loss = -1.0
            max_gain = 2.0

        return TradeProxy(
            entry_price=round(entry_price, 4),
            stop_level=round(stop_level, 4),
            target_level=round(target_level, 4),
            time_window=time_window,
            max_loss=max_loss,
            max_gain=max_gain,
        )

    def _simulate_legacy_trade(
        self,
        prices: list[float],
        expression_type: str,
        allowed: bool,
        confidence_score: int,
        proxy: TradeProxy,
    ) -> BacktestTradeResult:
        if not allowed:
            return BacktestTradeResult(
                expression_type=expression_type,
                outcome="NO_TRADE",
                pnl=0.0,
                return_pct=0.0,
                bars_held=0,
                no_trade=True,
                reason="Safeguards blocked execution",
                proxy=proxy,
            )

        window = prices[1 : proxy.time_window + 1]
        if confidence_score < 70:
            return BacktestTradeResult(
                expression_type=expression_type,
                outcome="NO_TRADE",
                pnl=0.0,
                return_pct=0.0,
                bars_held=0,
                no_trade=True,
                reason="Confidence gate rejected setup",
                proxy=proxy,
            )

        if expression_type == "CREDIT_BULL":
            breached = next((i for i, price in enumerate(window, start=1) if price < proxy.stop_level), None)
            if breached is None:
                return self._result(expression_type, "WIN", proxy.max_gain, proxy, len(window), "Price stayed above stop proxy")
            return self._result(expression_type, "LOSS", proxy.max_loss, proxy, breached, "Price breached support proxy")

        if expression_type == "CREDIT_BEAR":
            breached = next((i for i, price in enumerate(window, start=1) if price > proxy.stop_level), None)
            if breached is None:
                return self._result(expression_type, "WIN", proxy.max_gain, proxy, len(window), "Price stayed below stop proxy")
            return self._result(expression_type, "LOSS", proxy.max_loss, proxy, breached, "Price breached resistance proxy")

        if expression_type == "DEBIT_BULL":
            target_hit = next((i for i, price in enumerate(window, start=1) if price >= proxy.target_level), None)
            stop_hit = next((i for i, price in enumerate(window, start=1) if price <= proxy.stop_level), None)
            if target_hit is not None and (stop_hit is None or target_hit <= stop_hit):
                return self._result(expression_type, "WIN", proxy.max_gain, proxy, target_hit, "Upside target hit inside window")
            if stop_hit is not None:
                return self._result(expression_type, "LOSS", proxy.max_loss, proxy, stop_hit, "Downside stop hit before target")
            return self._result(expression_type, "LOSS", proxy.max_loss, proxy, len(window), "Target missed before expiry window")

        target_hit = next((i for i, price in enumerate(window, start=1) if price <= proxy.target_level), None)
        stop_hit = next((i for i, price in enumerate(window, start=1) if price >= proxy.stop_level), None)
        if target_hit is not None and (stop_hit is None or target_hit <= stop_hit):
            return self._result(expression_type, "WIN", proxy.max_gain, proxy, target_hit, "Downside target hit inside window")
        if stop_hit is not None:
            return self._result(expression_type, "LOSS", proxy.max_loss, proxy, stop_hit, "Upside stop hit before target")
        return self._result(expression_type, "LOSS", proxy.max_loss, proxy, len(window), "Target missed before expiry window")

    def _result(
        self,
        expression_type: str,
        outcome: str,
        pnl: float,
        proxy: TradeProxy,
        bars_held: int,
        reason: str,
    ) -> BacktestTradeResult:
        return BacktestTradeResult(
            expression_type=expression_type,
            outcome=outcome,
            pnl=pnl,
            return_pct=round((pnl / abs(proxy.max_loss)) * 100, 2),
            bars_held=bars_held,
            no_trade=False,
            reason=reason,
            proxy=proxy,
        )

    def _summarize_legacy(self, trades: list[BacktestTradeResult]) -> BacktestSummary:
        wins = sum(1 for trade in trades if trade.outcome == "WIN")
        losses = sum(1 for trade in trades if trade.outcome == "LOSS")
        no_trade_count = sum(1 for trade in trades if trade.no_trade)
        closed_trades = wins + losses
        total_pnl = sum(trade.pnl for trade in trades)
        gross_profit = sum(trade.pnl for trade in trades if trade.pnl > 0)
        gross_loss = abs(sum(trade.pnl for trade in trades if trade.pnl < 0))

        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for trade in trades:
            equity += trade.pnl
            peak = max(peak, equity)
            max_drawdown = min(max_drawdown, equity - peak)

        return BacktestSummary(
            trades=closed_trades,
            wins=wins,
            losses=losses,
            no_trade_count=no_trade_count,
            win_rate=round(wins / closed_trades, 4) if closed_trades else 0.0,
            expectancy=round(total_pnl / closed_trades, 4) if closed_trades else 0.0,
            max_drawdown=round(abs(max_drawdown), 4),
            profit_factor=round(gross_profit / gross_loss, 4) if gross_loss else float("inf") if gross_profit else 0.0,
        )
