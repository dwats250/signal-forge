from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean
from typing import Callable, Sequence


DEFAULT_FORWARD_WINDOWS = (5, 10, 20)
DEFAULT_FAVORABLE_PCT = 1.0
DEFAULT_ADVERSE_PCT = 0.5
USEFUL_ACCURACY_THRESHOLD = 0.55
USEFUL_FAILURE_THRESHOLD = 0.35
MIXED_ACCURACY_THRESHOLD = 0.50
MIXED_FAILURE_THRESHOLD = 0.50


Bar = dict[str, object]


@dataclass(slots=True, frozen=True)
class ValidationSignal:
    index: int
    timestamp: str
    ticker: str
    timeframe: str
    signal_type: str
    direction: str
    entry_price: float
    atr: float | None = None
    regime: str | None = None
    market_quality: str | None = None


@dataclass(slots=True)
class OutcomeThresholds:
    favorable_pct: float = DEFAULT_FAVORABLE_PCT
    adverse_pct: float = DEFAULT_ADVERSE_PCT


@dataclass(slots=True)
class IndicatorEventRecord:
    timestamp: str
    ticker: str
    timeframe: str
    signal_type: str
    direction: str
    entry_price: float
    price_after_5: float | None
    price_after_10: float | None
    price_after_20: float | None
    mfe_20: float
    mae_20: float
    directionally_correct: bool
    strong_follow_through: bool
    immediate_failure: bool
    regime: str | None = None
    market_quality: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class IndicatorValidationResult:
    events: list[IndicatorEventRecord]
    summary: dict[str, object]


SignalGenerator = Callable[[str, Sequence[Bar]], Sequence[ValidationSignal]]


def validate_indicator_accuracy(
    bar_data: dict[str, Sequence[Bar]],
    *,
    signal_generator: SignalGenerator | None = None,
    thresholds: OutcomeThresholds | None = None,
    forward_windows: Sequence[int] = DEFAULT_FORWARD_WINDOWS,
) -> IndicatorValidationResult:
    thresholds = thresholds or OutcomeThresholds()
    windows = tuple(sorted(set(int(window) for window in forward_windows)))
    events: list[IndicatorEventRecord] = []

    pine_signals: dict[str, list[ValidationSignal]] | None = None
    if signal_generator is None:
        from signal_forge.validation.pine_signal_adapter import generate_signal_forge_v1_signals

        pine_signals = generate_signal_forge_v1_signals(bar_data)

    for ticker, bars in bar_data.items():
        signals = list(pine_signals.get(ticker, [])) if pine_signals is not None else list(signal_generator(ticker, bars))
        for signal in signals:
            events.append(
                _record_signal_outcome(
                    signal,
                    bars=bars,
                    windows=windows,
                    thresholds=thresholds,
                )
            )

    return IndicatorValidationResult(events=events, summary=summarize_indicator_accuracy(events))


def build_signal_from_index(
    bars: Sequence[Bar],
    *,
    ticker: str,
    index: int,
    signal_type: str,
    direction: str,
    timeframe: str | None = None,
) -> ValidationSignal:
    if index < 0 or index >= len(bars):
        raise IndexError("signal index out of range")
    row = bars[index]
    entry_price = float(row["close"])
    return ValidationSignal(
        index=index,
        timestamp=str(row["timestamp"]),
        ticker=ticker,
        timeframe=str(timeframe or row.get("timeframe") or "unknown"),
        signal_type=signal_type,
        direction=direction,
        entry_price=entry_price,
        atr=_float_or_none(row.get("atr")),
        regime=_string_or_none(row.get("regime")),
        market_quality=_string_or_none(row.get("market_quality")),
    )


def summarize_indicator_accuracy(events: Sequence[IndicatorEventRecord]) -> dict[str, object]:
    totals = _metric_block(events)
    by_ticker = {key: _metric_block(group) for key, group in _group_by(events, lambda event: event.ticker).items()}
    by_signal_type = {
        key: _metric_block(group)
        for key, group in _group_by(events, lambda event: event.signal_type).items()
    }

    summary: dict[str, object] = {
        "total_signals": len(events),
        **totals,
        "by_ticker": by_ticker,
        "by_signal_type": by_signal_type,
        "indicator_classification": classify_indicator_quality(totals),
    }
    regimes = _group_by(events, lambda event: event.regime)
    if any(key is not None for key in regimes):
        summary["by_regime"] = {str(key): _metric_block(group) for key, group in regimes.items() if key is not None}
    qualities = _group_by(events, lambda event: event.market_quality)
    if any(key is not None for key in qualities):
        summary["by_market_quality"] = {
            str(key): _metric_block(group) for key, group in qualities.items() if key is not None
        }
    return summary


def classify_indicator_quality(metrics: dict[str, object]) -> str:
    accuracy = float(metrics.get("overall_directional_accuracy", 0.0))
    follow_through = float(metrics.get("strong_follow_through_rate", 0.0))
    failure = float(metrics.get("immediate_failure_rate", 0.0))
    total = int(metrics.get("total_signals", 0))

    if total == 0:
        return "NOISY"
    if accuracy >= USEFUL_ACCURACY_THRESHOLD and follow_through >= 0.40 and failure <= USEFUL_FAILURE_THRESHOLD:
        return "USEFUL"
    if accuracy >= MIXED_ACCURACY_THRESHOLD and follow_through >= 0.25 and failure <= MIXED_FAILURE_THRESHOLD:
        return "MIXED"
    return "NOISY"


def flatten_indicator_events(events: Sequence[IndicatorEventRecord]) -> list[dict[str, object]]:
    return [event.to_dict() for event in events]


def _record_signal_outcome(
    signal: ValidationSignal,
    *,
    bars: Sequence[Bar],
    windows: Sequence[int],
    thresholds: OutcomeThresholds,
) -> IndicatorEventRecord:
    future = list(bars[signal.index + 1 : signal.index + max(windows) + 1])
    closes = [float(bar["close"]) for bar in future if "close" in bar]
    if signal.direction not in {"bullish", "bearish"}:
        raise ValueError("signal direction must be bullish or bearish")

    price_after = {window: _price_after_window(closes, window) for window in windows}
    mfe, mae = _excursions(signal.entry_price, future, signal.direction)
    directionally_correct = _directionally_correct(signal.entry_price, price_after[max(windows)], signal.direction)
    favorable_threshold = _favorable_threshold(signal.entry_price, signal.atr, thresholds)
    adverse_threshold = _adverse_threshold(signal.entry_price, signal.atr, thresholds)
    strong_follow_through = mfe >= favorable_threshold
    immediate_failure = mae >= adverse_threshold

    return IndicatorEventRecord(
        timestamp=signal.timestamp,
        ticker=signal.ticker,
        timeframe=signal.timeframe,
        signal_type=signal.signal_type,
        direction=signal.direction,
        entry_price=round(signal.entry_price, 4),
        price_after_5=price_after.get(5),
        price_after_10=price_after.get(10),
        price_after_20=price_after.get(20),
        mfe_20=round(mfe, 4),
        mae_20=round(mae, 4),
        directionally_correct=directionally_correct,
        strong_follow_through=strong_follow_through,
        immediate_failure=immediate_failure,
        regime=signal.regime,
        market_quality=signal.market_quality,
    )


def _metric_block(events: Sequence[IndicatorEventRecord]) -> dict[str, object]:
    total = len(events)
    bullish = [event for event in events if event.direction == "bullish"]
    bearish = [event for event in events if event.direction == "bearish"]
    return {
        "total_signals": total,
        "overall_directional_accuracy": _ratio(sum(event.directionally_correct for event in events), total),
        "win_rate_bullish": _ratio(sum(event.directionally_correct for event in bullish), len(bullish)),
        "win_rate_bearish": _ratio(sum(event.directionally_correct for event in bearish), len(bearish)),
        "false_positive_rate": _ratio(sum(not event.directionally_correct for event in events), total),
        "strong_follow_through_rate": _ratio(sum(event.strong_follow_through for event in events), total),
        "immediate_failure_rate": _ratio(sum(event.immediate_failure for event in events), total),
        "average_move_5": _average_return(events, "price_after_5"),
        "average_move_10": _average_return(events, "price_after_10"),
        "average_move_20": _average_return(events, "price_after_20"),
    }


def _average_return(events: Sequence[IndicatorEventRecord], field_name: str) -> float:
    moves: list[float] = []
    for event in events:
        exit_price = getattr(event, field_name)
        if exit_price is None:
            continue
        if event.direction == "bullish":
            move = (exit_price - event.entry_price) / event.entry_price * 100
        else:
            move = (event.entry_price - exit_price) / event.entry_price * 100
        moves.append(move)
    return round(mean(moves), 4) if moves else 0.0


def _price_after_window(closes: Sequence[float], window: int) -> float | None:
    if len(closes) < window:
        return None
    return round(float(closes[window - 1]), 4)


def _excursions(entry_price: float, future: Sequence[Bar], direction: str) -> tuple[float, float]:
    favorable_moves: list[float] = [0.0]
    adverse_moves: list[float] = [0.0]
    for row in future:
        high = float(row.get("high", row["close"]))
        low = float(row.get("low", row["close"]))
        if direction == "bullish":
            favorable_moves.append((high - entry_price) / entry_price * 100)
            adverse_moves.append((entry_price - low) / entry_price * 100)
        else:
            favorable_moves.append((entry_price - low) / entry_price * 100)
            adverse_moves.append((high - entry_price) / entry_price * 100)
    return max(favorable_moves), max(adverse_moves)


def _directionally_correct(entry_price: float, exit_price: float | None, direction: str) -> bool:
    if exit_price is None:
        return False
    if direction == "bullish":
        return exit_price > entry_price
    return exit_price < entry_price


def _favorable_threshold(entry_price: float, atr: float | None, thresholds: OutcomeThresholds) -> float:
    pct_threshold = thresholds.favorable_pct
    if atr is None:
        return pct_threshold
    return max(pct_threshold, atr / entry_price * 100)


def _adverse_threshold(entry_price: float, atr: float | None, thresholds: OutcomeThresholds) -> float:
    pct_threshold = thresholds.adverse_pct
    if atr is None:
        return pct_threshold
    return max(pct_threshold, 0.5 * atr / entry_price * 100)


def _group_by(
    events: Sequence[IndicatorEventRecord],
    key_fn: Callable[[IndicatorEventRecord], str | None],
) -> dict[str | None, list[IndicatorEventRecord]]:
    grouped: dict[str | None, list[IndicatorEventRecord]] = {}
    for event in events:
        key = key_fn(event)
        grouped.setdefault(key, []).append(event)
    return grouped


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _float_or_none(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _string_or_none(value: object) -> str | None:
    return str(value) if isinstance(value, str) else None
