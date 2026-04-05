from __future__ import annotations

import unittest

from signal_forge.execution import EntryTrigger, OptionStructure, StrategyType, TradeCandidate, TradeDirection
from signal_forge.execution.models import PolicyState
from signal_forge.policy import filter_trade_candidate, infer_candidate_structure, resolve_trade_policy


class TradePolicyTests(unittest.TestCase):
    def _equity_candidate(
        self,
        *,
        score: float = 1.0,
        stop_level: float = 98.0,
        target_level: float = 104.0,
        ema_aligned: bool = True,
        averaging_down: bool = False,
    ) -> TradeCandidate:
        return TradeCandidate(
            symbol="SPY",
            strategy_type=StrategyType.EQUITY,
            direction=TradeDirection.BULLISH,
            entry_trigger=EntryTrigger(trigger_type="breakout", price=100.0),
            stop_level=stop_level,
            target_level=target_level,
            score=score,
            ema_aligned=ema_aligned,
            averaging_down=averaging_down,
        )

    def test_risk_on_clean_maps_to_aggressive(self) -> None:
        policy = resolve_trade_policy(
            {
                "regime": "RISK_ON",
                "market_quality": "CLEAN",
            }
        )

        self.assertEqual(policy.policy_state, PolicyState.AGGRESSIVE)
        self.assertEqual(policy.position_size_pct, 1.0)
        self.assertIn("LONG", policy.allowed_directions)

    def test_event_window_overrides_to_no_trade(self) -> None:
        policy = resolve_trade_policy(
            {
                "regime": "RISK_ON",
                "market_quality": "CLEAN",
                "event_risk": True,
                "event_window_minutes": 15,
            }
        )

        self.assertEqual(policy.policy_state, PolicyState.NO_TRADE)

    def test_vix_spike_downgrades_one_level(self) -> None:
        policy = resolve_trade_policy(
            {
                "regime": "RISK_ON",
                "market_quality": "CLEAN",
                "vix_spike": True,
            }
        )

        self.assertEqual(policy.policy_state, PolicyState.SELECTIVE)
        self.assertEqual(policy.position_size_pct, 0.6)

    def test_chaotic_dislocation_forces_no_trade(self) -> None:
        policy = resolve_trade_policy(
            {
                "regime": "RISK_OFF",
                "market_quality": "CHAOTIC",
                "dislocation": True,
            }
        )

        self.assertEqual(policy.policy_state, PolicyState.NO_TRADE)

    def test_filter_rejects_low_score(self) -> None:
        candidate = self._equity_candidate(score=0.5)
        policy = resolve_trade_policy({"regime": "RISK_ON", "market_quality": "CLEAN"})

        passed, reason = filter_trade_candidate(candidate, policy, active_trade_count=0)

        self.assertFalse(passed)
        self.assertIn("score", reason)

    def test_filter_does_not_own_max_concurrent_gate(self) -> None:
        candidate = self._equity_candidate()
        policy = resolve_trade_policy({"regime": "RISK_ON", "market_quality": "CLEAN"})

        passed, reason = filter_trade_candidate(candidate, policy, active_trade_count=4)

        self.assertTrue(passed)
        self.assertIn("allows candidate", reason)

    def test_structure_inference_maps_directional_debits(self) -> None:
        bullish = TradeCandidate(
            symbol="QQQ",
            strategy_type=StrategyType.DEBIT_SPREAD,
            direction=TradeDirection.BULLISH,
            entry_trigger=EntryTrigger(trigger_type="breakout", price=100.0),
            stop_level=98.0,
            target_level=104.0,
            option_structure=OptionStructure(
                expiry="2026-05-15",
                days_to_expiry=30,
                contracts=1,
                open_interest=1000,
                spread_pct=0.05,
                net_debit=150.0,
            ),
        )
        bearish = TradeCandidate(
            symbol="QQQ",
            strategy_type=StrategyType.DEBIT_SPREAD,
            direction=TradeDirection.BEARISH,
            entry_trigger=EntryTrigger(trigger_type="breakdown", price=100.0),
            stop_level=102.0,
            target_level=96.0,
            option_structure=OptionStructure(
                expiry="2026-05-15",
                days_to_expiry=30,
                contracts=1,
                open_interest=1000,
                spread_pct=0.05,
                net_debit=150.0,
            ),
        )

        self.assertEqual(infer_candidate_structure(bullish), "CALL_DEBIT")
        self.assertEqual(infer_candidate_structure(bearish), "PUT_DEBIT")

    def test_scenario_1_valid_trade_allows(self) -> None:
        policy = resolve_trade_policy({"regime": "RISK_ON", "market_quality": "CLEAN"})

        passed, reason = filter_trade_candidate(self._equity_candidate(score=0.9), policy, active_trade_count=0)

        self.assertTrue(passed)
        self.assertEqual(reason, "AGGRESSIVE policy allows candidate")

    def test_scenario_2_risk_off_blocks(self) -> None:
        policy = resolve_trade_policy({"regime": "RISK_OFF", "market_quality": "CLEAN"})

        passed, reason = filter_trade_candidate(self._equity_candidate(score=0.8), policy, active_trade_count=0)

        self.assertFalse(passed)
        self.assertEqual(reason, "direction LONG blocked by NO_TRADE policy")

    def test_scenario_3_constraint_failure_blocks(self) -> None:
        policy = resolve_trade_policy({"regime": "RISK_ON", "market_quality": "MIXED"})

        passed, reason = filter_trade_candidate(
            self._equity_candidate(stop_level=99.6, target_level=100.6),
            policy,
            active_trade_count=policy.max_concurrent_trades,
        )

        self.assertFalse(passed)
        self.assertEqual(reason, "candidate fails minimum 2:1 reward-to-risk constraint")


if __name__ == "__main__":
    unittest.main()
