from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from signal_forge.execution import (
    EntryTrigger,
    ExecutionError,
    ExecutionOrchestrator,
    OptionStructure,
    StrategyType,
    TradeCandidate,
    TradeDirection,
    TradeState,
)
from signal_forge.execution.gates import calculate_trade_ticket


class ExecutionSubsystemTests(unittest.TestCase):
    def test_valid_trade_flow_reaches_closed_and_reviewed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = ExecutionOrchestrator(Path(tmpdir))
            candidate = TradeCandidate(
                symbol="SPY",
                strategy_type=StrategyType.EQUITY,
                direction=TradeDirection.BULLISH,
                entry_trigger=EntryTrigger(trigger_type="breakout", price=100.0),
                stop_level=98.0,
                target_level=106.0,
            )

            ready = orchestrator.submit_trade(
                candidate,
                market_regime={"approved": True, "reason": "trend aligned"},
                setup_result={"valid": True, "direction": "bullish"},
                account_size=10_000,
                risk_percent=0.01,
            )
            self.assertEqual(ready.state, TradeState.READY)
            self.assertEqual(ready.ticket.position_size, 50)
            self.assertEqual(ready.ticket.max_risk, 100.0)

            executed = orchestrator.execute_trade(candidate.trade_id, fill_price=100.1)
            self.assertEqual(executed.state, TradeState.EXECUTED)

            closed = orchestrator.close_trade(candidate.trade_id, exit_price=105.5)
            self.assertEqual(closed.state, TradeState.CLOSED)

            reviewed = orchestrator.review_trade(
                candidate.trade_id,
                followed_entry=True,
                followed_stop=True,
                followed_exit=True,
                result_R=2.5,
            )
            self.assertIsNotNone(reviewed.review_result)
            log_lines = (Path(tmpdir) / "trades.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertGreaterEqual(len(log_lines), 6)

    def test_rejected_trade_fails_early(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = ExecutionOrchestrator(Path(tmpdir))
            candidate = TradeCandidate(
                symbol="QQQ",
                strategy_type=StrategyType.EQUITY,
                direction=TradeDirection.BEARISH,
                entry_trigger=EntryTrigger(trigger_type="breakdown", price=100.0),
                stop_level=102.0,
                target_level=96.0,
            )

            with self.assertRaisesRegex(ExecutionError, "market gate failed"):
                orchestrator.submit_trade(
                    candidate,
                    market_regime={"approved": False, "reason": "market gate failed"},
                    setup_result={"valid": True, "direction": "bearish"},
                    account_size=10_000,
                    risk_percent=1,
                )

    def test_risk_calculation_correctness_for_equity(self) -> None:
        candidate = TradeCandidate(
            symbol="IWM",
            strategy_type=StrategyType.EQUITY,
            direction=TradeDirection.BULLISH,
            entry_trigger=EntryTrigger(trigger_type="pullback", price=50.0),
            stop_level=48.0,
            target_level=56.0,
        )

        ticket = calculate_trade_ticket(
            candidate,
            account_size=20_000,
            risk_percent=1,
        )

        self.assertEqual(ticket.position_size, 100)
        self.assertEqual(ticket.max_risk, 200.0)
        self.assertEqual(ticket.R_multiple, 3.0)

    def test_csp_vs_debit_spread_risk_correctness(self) -> None:
        debit_candidate = TradeCandidate(
            symbol="AAPL",
            strategy_type=StrategyType.DEBIT_SPREAD,
            direction=TradeDirection.BULLISH,
            entry_trigger=EntryTrigger(trigger_type="signal", price=180.0),
            stop_level=175.0,
            target_level=195.0,
            option_structure=OptionStructure(
                expiry="2026-05-15",
                days_to_expiry=35,
                contracts=1,
                open_interest=1_000,
                spread_pct=0.05,
                net_debit=250.0,
            ),
        )
        csp_candidate = TradeCandidate(
            symbol="AAPL",
            strategy_type=StrategyType.CASH_SECURED_PUT,
            direction=TradeDirection.BULLISH,
            entry_trigger=EntryTrigger(trigger_type="signal", price=180.0),
            stop_level=170.0,
            target_level=195.0,
            option_structure=OptionStructure(
                expiry="2026-05-15",
                days_to_expiry=35,
                contracts=1,
                open_interest=1_000,
                spread_pct=0.05,
                strike=150.0,
                premium=5.0,
            ),
        )

        debit_ticket = calculate_trade_ticket(
            debit_candidate,
            account_size=1_000,
            risk_percent=0.5,
        )
        csp_ticket = calculate_trade_ticket(
            csp_candidate,
            account_size=20_000,
            risk_percent=0.8,
        )

        self.assertEqual(debit_ticket.position_size, 2)
        self.assertEqual(debit_ticket.max_risk, 500.0)
        self.assertEqual(csp_ticket.position_size, 1)
        self.assertEqual(csp_ticket.max_risk, 14_500.0)

    def test_review_before_next_trade_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = ExecutionOrchestrator(Path(tmpdir))
            first = TradeCandidate(
                symbol="SPY",
                strategy_type=StrategyType.EQUITY,
                direction=TradeDirection.BULLISH,
                entry_trigger=EntryTrigger(trigger_type="breakout", price=100.0),
                stop_level=99.0,
                target_level=103.0,
            )
            second = TradeCandidate(
                symbol="QQQ",
                strategy_type=StrategyType.EQUITY,
                direction=TradeDirection.BULLISH,
                entry_trigger=EntryTrigger(trigger_type="breakout", price=200.0),
                stop_level=198.0,
                target_level=206.0,
            )

            orchestrator.submit_trade(
                first,
                market_regime={"approved": True},
                setup_result={"valid": True, "direction": "bullish"},
                account_size=10_000,
                risk_percent=0.01,
            )
            orchestrator.execute_trade(first.trade_id, fill_price=100.0)
            orchestrator.close_trade(first.trade_id, exit_price=101.0)

            with self.assertRaisesRegex(ExecutionError, "review required before next trade"):
                orchestrator.submit_trade(
                    second,
                    market_regime={"approved": True},
                    setup_result={"valid": True, "direction": "bullish"},
                    account_size=10_000,
                    risk_percent=0.01,
                )

    def test_invalid_input_rejection(self) -> None:
        with self.assertRaisesRegex(ValueError, "bullish trades require stop < entry < target"):
            TradeCandidate(
                symbol="TSLA",
                strategy_type=StrategyType.EQUITY,
                direction=TradeDirection.BULLISH,
                entry_trigger=EntryTrigger(trigger_type="breakout", price=100.0),
                stop_level=101.0,
                target_level=110.0,
            )

    def test_policy_change_log_is_append_only_and_single_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = ExecutionOrchestrator(Path(tmpdir))
            change = orchestrator.apply_policy_change(
                field="min_open_interest",
                new_value=500,
                reason="raise liquidity bar",
                review_window=5,
            )
            self.assertEqual(change["previous_value"], 250)
            log_lines = (Path(tmpdir) / "policy_changes.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(log_lines), 1)
            self.assertEqual(json.loads(log_lines[0])["new_value"], 500)

            with self.assertRaisesRegex(ValueError, "only one active policy change is allowed"):
                orchestrator.apply_policy_change(
                    field="max_spread_pct",
                    new_value=0.08,
                    reason="tighten spreads",
                    review_window=5,
                )


    def test_partial_fill_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = ExecutionOrchestrator(Path(tmpdir))
            candidate = TradeCandidate(
                symbol="SPY",
                strategy_type=StrategyType.EQUITY,
                direction=TradeDirection.BULLISH,
                entry_trigger=EntryTrigger(trigger_type="breakout", price=100.0),
                stop_level=98.0,
                target_level=106.0,
            )
            orchestrator.submit_trade(
                candidate,
                market_regime={"approved": True},
                setup_result={"valid": True, "direction": "bullish"},
                account_size=10_000,
                risk_percent=0.01,
            )
            from signal_forge.execution import FillStatus

            with self.assertRaisesRegex(ExecutionError, "partial fills are rejected"):
                orchestrator.execute_trade(
                    candidate.trade_id,
                    fill_price=100.0,
                    fill_status=FillStatus.PARTIAL,
                )

    def test_double_review_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = ExecutionOrchestrator(Path(tmpdir))
            candidate = TradeCandidate(
                symbol="SPY",
                strategy_type=StrategyType.EQUITY,
                direction=TradeDirection.BULLISH,
                entry_trigger=EntryTrigger(trigger_type="breakout", price=100.0),
                stop_level=98.0,
                target_level=106.0,
            )
            orchestrator.submit_trade(
                candidate,
                market_regime={"approved": True},
                setup_result={"valid": True, "direction": "bullish"},
                account_size=10_000,
                risk_percent=0.01,
            )
            orchestrator.execute_trade(candidate.trade_id, fill_price=100.0)
            orchestrator.close_trade(candidate.trade_id, exit_price=104.0)
            orchestrator.review_trade(
                candidate.trade_id,
                followed_entry=True,
                followed_stop=True,
                followed_exit=True,
                result_R=2.0,
            )
            with self.assertRaisesRegex(ExecutionError, "already has a review result"):
                orchestrator.review_trade(
                    candidate.trade_id,
                    followed_entry=False,
                    followed_stop=False,
                    followed_exit=False,
                    result_R=-1.0,
                )

    def test_stale_trade_close_is_accepted_and_reviewed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = ExecutionOrchestrator(Path(tmpdir))
            candidate = TradeCandidate(
                symbol="IWM",
                strategy_type=StrategyType.EQUITY,
                direction=TradeDirection.BULLISH,
                entry_trigger=EntryTrigger(trigger_type="breakout", price=100.0),
                stop_level=98.0,
                target_level=106.0,
            )
            orchestrator.submit_trade(
                candidate,
                market_regime={"approved": True},
                setup_result={"valid": True, "direction": "bullish"},
                account_size=10_000,
                risk_percent=0.01,
            )
            closed = orchestrator.close_trade(candidate.trade_id, stale=True)
            self.assertEqual(closed.closure_reason, "stale_trade")
            reviewed = orchestrator.review_trade(
                candidate.trade_id,
                followed_entry=False,
                followed_stop=False,
                followed_exit=False,
                result_R=0.0,
            )
            self.assertIsNotNone(reviewed.review_result)


if __name__ == "__main__":
    unittest.main()
