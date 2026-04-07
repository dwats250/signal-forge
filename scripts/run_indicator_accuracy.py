from __future__ import annotations

import argparse
import csv
import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from outputs.indicator_accuracy_report import render_indicator_accuracy_report
from signal_forge.data.loader import load_price_series
from signal_forge.validation.indicator_accuracy import flatten_indicator_events, validate_indicator_accuracy
from signal_forge.validation.pine_signal_adapter import PINE_APPROVED_TICKERS, assess_pine_v1_bar_data

DEFAULT_TICKERS = PINE_APPROVED_TICKERS
DEFAULT_OUTPUT_PATH = Path("outputs/indicator_accuracy.csv")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run indicator accuracy validation")
    parser.add_argument("--tickers", nargs="*", default=DEFAULT_TICKERS, help="Tickers to validate")
    parser.add_argument("--csv", default=str(DEFAULT_OUTPUT_PATH), help="Optional CSV output path")
    args = parser.parse_args(argv)

    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        bar_data = {ticker: _series_to_bars(load_price_series(ticker), ticker) for ticker in args.tickers}

    assessment = assess_pine_v1_bar_data(bar_data)
    if not assessment.supported:
        print("## SUMMARY")
        print("- total signals: 0")
        print("- overall directional accuracy: 0.0%")
        print("- strong follow-through rate: 0.0%")
        print("- worst ticker: n/a")
        print("- best ticker: n/a")
        print("- classification: NOISY")
        print("- verdict: BLOCKED")
        print(f"- reason: {assessment.reason}")
        if args.csv:
            _write_csv(Path(args.csv), [])
            print(f"- csv: wrote empty template to {args.csv}")
        return 0

    result = validate_indicator_accuracy(bar_data)
    print(render_indicator_accuracy_report(result.summary))

    if args.csv:
        rows = flatten_indicator_events(result.events)
        _write_csv(Path(args.csv), rows)
        print(f"\nCSV: {args.csv}")
    return 0


def _series_to_bars(series: list[float], ticker: str) -> list[dict[str, object]]:
    bars: list[dict[str, object]] = []
    base_time = datetime(2026, 1, 1, 16, 0, tzinfo=timezone.utc)
    for index, close in enumerate(series):
        bars.append(
            {
                "timestamp": (base_time + timedelta(days=index)).isoformat(),
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "timeframe": "1D",
                "volume": 0.0,
            }
        )
    return bars


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "timestamp",
        "ticker",
        "timeframe",
        "signal_type",
        "direction",
        "entry_price",
        "price_after_5",
        "price_after_10",
        "price_after_20",
        "mfe_20",
        "mae_20",
        "directionally_correct",
        "strong_follow_through",
        "immediate_failure",
        "regime",
        "market_quality",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


if __name__ == "__main__":
    raise SystemExit(main())
