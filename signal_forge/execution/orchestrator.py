from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from signal_forge.execution.gates import (
    calculate_trade_ticket,
    evaluate_market_gate,
    evaluate_setup_gate,
)
from signal_forge.execution.models import (
    ExecutionPolicy,
    FillStatus,
    PolicyState,
    TradeCandidate,
    TradeRecord,
    TradeState,
)
from signal_forge.execution.models.core import utc_now
from signal_forge.execution.policy import PolicyStore
from signal_forge.execution.review import generate_review_result
from signal_forge.policy import filter_trade_candidate, resolve_trade_policy


class ExecutionError(ValueError):
    pass


class ExecutionOrchestrator:
    def __init__(self, log_dir: Path, policy: ExecutionPolicy | None = None) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.trades_path = self.log_dir / "trades.jsonl"
        self.trade_policy_path = self.log_dir / "trade_policy_log.jsonl"
        self.policy_store = PolicyStore(self.log_dir / "policy_changes.jsonl", policy=policy)
        self.records = self._load_records()

    def submit_trade(
        self,
        candidate: TradeCandidate,
        *,
        market_regime: dict[str, object] | None,
        setup_result: dict[str, object] | None,
        account_size: float,
        risk_percent: float,
    ) -> TradeRecord:
        self._enforce_reviews_complete()
        record = TradeRecord(trade_id=candidate.trade_id, state=TradeState.CREATED, candidate=candidate)
        self._persist(record)

        market = evaluate_market_gate(market_regime)
        if not bool(market["passed"]):
            record.market_result = market
            self._reject_record(record, str(market["reason"]))

        active_trade_count = self._active_trade_count(exclude_trade_id=record.trade_id)
        self._transition(record, TradeState.MARKET_APPROVED)
        record.market_result = market
        trade_policy = resolve_trade_policy(market_regime)
        record.trade_policy = trade_policy.to_dict()
        self._persist(record)

        policy_gate_reason = self._policy_gate_reason(
            trade_policy=trade_policy,
            active_trade_count=active_trade_count,
        )
        if policy_gate_reason is not None:
            self._log_trade_policy(
                market_regime=market_regime,
                trade_policy=trade_policy.to_dict(),
                trades_taken=0,
                trades_blocked=1,
                reason_blocked=policy_gate_reason,
                rejection_stage="trade_policy",
            )
            self._reject_record(record, policy_gate_reason)

        policy_passed, policy_reason = filter_trade_candidate(
            candidate,
            trade_policy,
            active_trade_count=active_trade_count,
        )
        if not policy_passed:
            self._log_trade_policy(
                market_regime=market_regime,
                trade_policy=trade_policy.to_dict(),
                trades_taken=0,
                trades_blocked=1,
                reason_blocked=policy_reason,
                rejection_stage="candidate_filter",
            )
            self._reject_record(record, policy_reason)

        setup = evaluate_setup_gate(candidate, setup_result)
        if not bool(setup["valid"]):
            record.setup_result = setup
            self._reject_record(record, str(setup["reason"]))

        self._transition(record, TradeState.SETUP_APPROVED)
        record.setup_result = setup
        self._persist(record)

        ticket = calculate_trade_ticket(
            candidate,
            account_size=account_size,
            risk_percent=self._scaled_risk_percent(risk_percent, trade_policy.position_size_pct),
            policy=self.policy_store.policy,
        )
        self._transition(record, TradeState.RISK_APPROVED)
        record.ticket = ticket
        self._persist(record)

        self._transition(record, TradeState.READY)
        self._persist(record)
        self._log_trade_policy(
            market_regime=market_regime,
            trade_policy=trade_policy.to_dict(),
            trades_taken=1,
            trades_blocked=0,
            reason_blocked=None,
            rejection_stage=None,
        )
        return copy.deepcopy(record)

    def execute_trade(
        self,
        trade_id: str,
        *,
        fill_price: float,
        fill_status: FillStatus = FillStatus.FILLED,
    ) -> TradeRecord:
        record = self._require_record(trade_id)
        if fill_status == FillStatus.PARTIAL:
            raise ExecutionError("partial fills are rejected by execution policy")
        if fill_status == FillStatus.RETRY:
            raise ExecutionError("retry requested; trade remains in READY state")
        if record.state != TradeState.READY:
            raise ExecutionError("trade must be READY before execution")
        if fill_price <= 0:
            raise ExecutionError("fill_price must be positive")

        self._transition(record, TradeState.EXECUTED)
        record.execution_price = fill_price
        self._persist(record)
        return copy.deepcopy(record)

    def close_trade(
        self,
        trade_id: str,
        *,
        exit_price: float | None = None,
        stale: bool = False,
    ) -> TradeRecord:
        record = self._require_record(trade_id)
        if stale:
            if record.state not in {TradeState.READY, TradeState.EXECUTED}:
                raise ExecutionError("only READY or EXECUTED trades can be closed as stale")
            record.closure_reason = "stale_trade"
        elif record.state != TradeState.EXECUTED:
            raise ExecutionError("trade must be EXECUTED before closing")
        if exit_price is not None and exit_price <= 0:
            raise ExecutionError("exit_price must be positive")

        self._transition(record, TradeState.CLOSED)
        record.exit_price = exit_price
        if record.closure_reason is None:
            record.closure_reason = "closed"
        self._persist(record)
        return copy.deepcopy(record)

    def review_trade(
        self,
        trade_id: str,
        *,
        followed_entry: bool,
        followed_stop: bool,
        followed_exit: bool,
        result_R: float,
    ) -> TradeRecord:
        record = self._require_record(trade_id)
        if record.state != TradeState.CLOSED:
            raise ExecutionError("trade must be CLOSED before review")
        if record.review_result is not None:
            raise ExecutionError("trade already has a review result")
        record.review_result = generate_review_result(
            followed_entry=followed_entry,
            followed_stop=followed_stop,
            followed_exit=followed_exit,
            result_R=result_R,
        )
        self._persist(record)
        return copy.deepcopy(record)

    def apply_policy_change(
        self,
        *,
        field: str,
        new_value: object,
        reason: str,
        review_window: int,
    ) -> dict[str, Any]:
        change = self.policy_store.apply_change(
            field=field,
            new_value=new_value,
            reason=reason,
            review_window=review_window,
        )
        return change.to_dict()

    def _enforce_reviews_complete(self) -> None:
        open_reviews = [
            record.trade_id
            for record in self.records.values()
            if record.state == TradeState.CLOSED and record.review_result is None
        ]
        if open_reviews:
            raise ExecutionError("review required before next trade")

    def _require_record(self, trade_id: str) -> TradeRecord:
        try:
            return self.records[trade_id]
        except KeyError as exc:
            raise ExecutionError(f"unknown trade_id: {trade_id}") from exc

    def _transition(self, record: TradeRecord, new_state: TradeState) -> None:
        if new_state.value <= record.state.value:
            raise ExecutionError("state transitions must move forward")
        record.state = new_state

    def _reject_record(self, record: TradeRecord, reason: str) -> None:
        record.rejection_reason = reason
        self._persist(record)
        raise ExecutionError(reason)

    def _policy_gate_reason(
        self,
        *,
        trade_policy: Any,
        active_trade_count: int,
    ) -> str | None:
        if trade_policy.policy_state == PolicyState.NO_TRADE:
            return f"trade policy NO_TRADE: {trade_policy.notes}"
        if active_trade_count >= trade_policy.max_concurrent_trades:
            return (
                "trade policy max concurrent trades reached: "
                f"{active_trade_count}/{trade_policy.max_concurrent_trades}"
            )
        return None

    def _persist(self, record: TradeRecord) -> None:
        record.updated_at = utc_now()
        self.records[record.trade_id] = record
        with self.trades_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), sort_keys=True))
            handle.write("\n")

    def _active_trade_count(self, *, exclude_trade_id: str | None = None) -> int:
        active_states = {
            TradeState.MARKET_APPROVED,
            TradeState.SETUP_APPROVED,
            TradeState.RISK_APPROVED,
            TradeState.READY,
            TradeState.EXECUTED,
        }
        return sum(
            1
            for record in self.records.values()
            if record.trade_id != exclude_trade_id
            and record.rejection_reason is None
            and record.state in active_states
        )

    def _scaled_risk_percent(self, risk_percent: float, position_size_pct: float) -> float:
        normalized = risk_percent / 100 if risk_percent > 1 else risk_percent
        return normalized * position_size_pct

    def _log_trade_policy(
        self,
        *,
        market_regime: dict[str, object] | None,
        trade_policy: dict[str, Any],
        trades_taken: int,
        trades_blocked: int,
        reason_blocked: str | None,
        rejection_stage: str | None,
    ) -> None:
        market_context = market_regime or {}
        payload = {
            "timestamp": utc_now(),
            "regime": market_context.get("regime", "MIXED"),
            "market_quality": market_context.get("market_quality", "MIXED"),
            "policy_state": trade_policy["policy_state"],
            "candidates_seen": 1,
            "trades_taken": trades_taken,
            "trades_blocked": trades_blocked,
            "rejected": trades_blocked > 0,
            "rejection_stage": rejection_stage,
            "reason_blocked": reason_blocked,
        }
        with self.trade_policy_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True))
            handle.write("\n")

    def _load_records(self) -> dict[str, TradeRecord]:
        records: dict[str, TradeRecord] = {}
        if not self.trades_path.exists():
            return records
        from signal_forge.execution.cli.submit_trade import candidate_from_payload
        from signal_forge.execution.models import ReviewDeviationType, ReviewResult, TradeTicket

        with self.trades_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                candidate = candidate_from_payload(payload["candidate"])
                record = TradeRecord(
                    trade_id=payload["trade_id"],
                    state=TradeState[payload["state"]],
                    candidate=candidate,
                    market_result=payload.get("market_result"),
                    trade_policy=payload.get("trade_policy"),
                    setup_result=payload.get("setup_result"),
                    rejection_reason=payload.get("rejection_reason"),
                    execution_price=payload.get("execution_price"),
                    exit_price=payload.get("exit_price"),
                    closure_reason=payload.get("closure_reason"),
                    updated_at=payload.get("updated_at", candidate.created_at),
                )
                ticket_payload = payload.get("ticket")
                if ticket_payload is not None:
                    record.ticket = TradeTicket(**ticket_payload)
                review_payload = payload.get("review_result")
                if review_payload is not None:
                    record.review_result = ReviewResult(
                        followed_entry=review_payload["followed_entry"],
                        followed_stop=review_payload["followed_stop"],
                        followed_exit=review_payload["followed_exit"],
                        deviation_type=ReviewDeviationType(review_payload["deviation_type"]),
                        result_R=review_payload["result_R"],
                        reviewed_at=review_payload["reviewed_at"],
                    )
                records[record.trade_id] = record
        return records
