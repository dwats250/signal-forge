from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from signal_forge.backtest import Trade, run_backtest
from signal_forge.data import load_price_series
from signal_forge.execution.cli import load_json_payload, submit_trade_from_payload
from signal_forge.execution.orchestrator import ExecutionOrchestrator
from signal_forge.gate import gate_trade
from signal_forge.pipeline import SignalForgePipeline


def _run_demo() -> None:
    pipeline = SignalForgePipeline(Path("outputs/audit.log.jsonl"))
    result = pipeline.run(
        {
            "macro": {
                "state": "bearish",
                "confidence": "high",
                "key_factors": ["growth is rolling over"],
                "time_horizon": "macro",
            },
            "geo": {
                "state": "neutral",
                "confidence": "medium",
                "key_factors": ["event premium contained"],
            },
            "market_quality": {
                "state": "bearish",
                "confidence": "medium",
                "key_factors": ["breadth is weak"],
            },
            "options": {
                "state": "bullish",
                "confidence": "high",
                "key_factors": ["short-term escape window is open"],
                "time_horizon": "intraday",
                "special_flags": {
                    "escape_window_state": "strong",
                    "iv_state": "expanding",
                },
            },
        }
    )
    print(json.dumps(result, indent=2, sort_keys=True))


def _load_gate_trade(args: argparse.Namespace) -> dict[str, object]:
    if args.description is not None or args.tags:
        return {
            "description": args.description or "",
            "tags": args.tags,
        }
    if not sys.stdin.isatty():
        return json.load(sys.stdin)
    raise SystemExit(
        "gate requires --description with one or more --tag values, or JSON on stdin."
    )


def _run_backtest_demo() -> None:
    trades = [
        Trade("SPY", "bullish", "call_debit", 100.0, 98.0, 104.0),
        Trade("QQQ", "bearish", "call_credit", 100.0, 102.0, 96.0),
    ]
    price_data = {trade.symbol: load_price_series(trade.symbol) for trade in trades}
    result = run_backtest(trades, price_data)
    print(json.dumps(result, indent=2, sort_keys=True))


def _default_execution_log_dir() -> Path:
    return Path(__file__).resolve().parent / "execution" / "logs"


def _run_submit_trade(args: argparse.Namespace) -> None:
    payload = load_json_payload(args.file)
    result = submit_trade_from_payload(payload, log_dir=Path(args.log_dir))
    print(json.dumps(result, indent=2, sort_keys=True))


def _run_review_trade(args: argparse.Namespace) -> None:
    payload = load_json_payload(args.file)
    orchestrator = ExecutionOrchestrator(Path(args.log_dir))
    record = orchestrator.review_trade(
        payload["trade_id"],
        followed_entry=payload["followed_entry"],
        followed_stop=payload["followed_stop"],
        followed_exit=payload["followed_exit"],
        result_R=payload["result_R"],
    )
    print(json.dumps(record.to_dict(), indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(prog="signal_forge")
    subparsers = parser.add_subparsers(dest="command")

    gate_parser = subparsers.add_parser("gate", help="Gate a trade against stored edge components")
    gate_parser.add_argument("--description", help="Trade description")
    gate_parser.add_argument(
        "--tag",
        dest="tags",
        action="append",
        default=[],
        help="Trade tag. Repeat for multiple tags.",
    )
    subparsers.add_parser("backtest-demo", help="Run the Phase 1 backtest example")
    submit_trade_parser = subparsers.add_parser(
        "submit-trade",
        help="Submit a structured execution trade candidate",
    )
    submit_trade_parser.add_argument("--file", help="Path to JSON payload")
    submit_trade_parser.add_argument(
        "--log-dir",
        default=str(_default_execution_log_dir()),
        help="Directory for execution JSONL logs",
    )
    review_trade_parser = subparsers.add_parser(
        "review-trade",
        help="Record a review result for a closed trade",
    )
    review_trade_parser.add_argument("--file", help="Path to JSON payload")
    review_trade_parser.add_argument(
        "--log-dir",
        default=str(_default_execution_log_dir()),
        help="Directory for execution JSONL logs",
    )

    args = parser.parse_args()
    if args.command == "gate":
        result = gate_trade(_load_gate_trade(args))
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    if args.command == "backtest-demo":
        _run_backtest_demo()
        return
    if args.command == "submit-trade":
        _run_submit_trade(args)
        return
    if args.command == "review-trade":
        _run_review_trade(args)
        return

    _run_demo()


if __name__ == "__main__":
    main()
