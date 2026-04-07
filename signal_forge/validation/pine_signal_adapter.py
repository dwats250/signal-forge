from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from signal_forge.validation.indicator_accuracy import ValidationSignal


Bar = dict[str, object]

MIN_ATR_THRESHOLD = 0.30
ALERT_SCORE_THRESHOLD = 7
READY_SCORE = 6
LEVEL_PROX = 0.003
RETEST_TOL = 0.0015
OPEN_DRIVE_VOL_RATIO = 1.75
PINE_APPROVED_TICKERS = ["SPY", "QQQ", "NVDA", "TSLA", "AMD", "SMCI", "META", "MSTR", "COIN"]


@dataclass(slots=True)
class PineDataAssessment:
    supported: bool
    reason: str | None = None


def assess_pine_v1_bar_data(bar_data: dict[str, Sequence[Bar]]) -> PineDataAssessment:
    if not bar_data:
        return PineDataAssessment(False, "no bar data provided")
    sample_ticker = next(iter(bar_data))
    sample = list(bar_data[sample_ticker])
    if not sample:
        return PineDataAssessment(False, "bar data is empty")
    row = sample[0]
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = sorted(required.difference(row))
    if missing:
        return PineDataAssessment(
            False,
            f"Signal Forge v1 requires intraday OHLCV bars; missing fields: {', '.join(missing)}",
        )
    interval_minutes = _infer_interval_minutes(sample)
    if interval_minutes is None or interval_minutes >= 1440:
        return PineDataAssessment(False, "Signal Forge v1 requires intraday bars with timestamp spacing below one day")
    return PineDataAssessment(True, None)


def generate_signal_forge_v1_signals(
    bar_data: dict[str, Sequence[Bar]],
    *,
    min_atr: float = MIN_ATR_THRESHOLD,
    score_threshold: int = ALERT_SCORE_THRESHOLD,
) -> dict[str, list["ValidationSignal"]]:
    from signal_forge.validation.indicator_accuracy import ValidationSignal

    prepared = {ticker: _prepare_rows(ticker, bars) for ticker, bars in bar_data.items()}
    signals: dict[str, list[ValidationSignal]] = {}
    for ticker, rows in prepared.items():
        macro_ticker = "QQQ" if ticker == "SPY" else "SPY"
        macro_rows = prepared.get(macro_ticker, [])
        macro_lookup = {str(row["timestamp"]): row for row in macro_rows}
        signals[ticker] = _run_state_machine(
            ticker,
            rows,
            macro_lookup=macro_lookup,
            min_atr=min_atr,
            score_threshold=score_threshold,
        )
    return signals


def _run_state_machine(
    ticker: str,
    rows: Sequence[Bar],
    *,
    macro_lookup: dict[str, Bar],
    min_atr: float,
    score_threshold: int,
) -> list["ValidationSignal"]:
    from signal_forge.validation.indicator_accuracy import ValidationSignal

    if ticker not in PINE_APPROVED_TICKERS:
        return []

    signals: list[ValidationSignal] = []
    state = 0
    locked_level: float | None = None
    locked_bias: str | None = None
    locked_setup_type: str | None = None
    alerted_this_cycle = False

    bull_push_events: list[bool] = []
    bear_push_events: list[bool] = []

    for index, row in enumerate(rows):
        timestamp = str(row["timestamp"])
        macro_row = macro_lookup.get(timestamp)
        bullish_bias = bool(row["ema9"] > row["ema21"] and row["close"] > row["vwap"])
        bearish_bias = bool(row["ema9"] < row["ema21"] and row["close"] < row["vwap"])
        has_bias = bullish_bias or bearish_bias
        macro_bullish = bool(macro_row and macro_row["close"] > macro_row["vwap"])
        macro_bearish = bool(macro_row and macro_row["close"] < macro_row["vwap"])

        at_level_bull = any(_near(float(row["close"]), _value_or_none(row, key)) for key in ("or_high", "pm_high", "prev_day_high", "vwap"))
        at_level_bear = any(_near(float(row["close"]), _value_or_none(row, key)) for key in ("or_low", "pm_low", "prev_day_low", "vwap"))
        at_key_level = (bullish_bias and at_level_bull) or (bearish_bias and at_level_bear)
        active_level = _active_level(row, bullish_bias=bullish_bias, bearish_bias=bearish_bias)
        any_level_exists = any(_value_or_none(row, key) is not None for key in ("or_high", "or_low", "pm_high", "pm_low", "prev_day_high", "prev_day_low", "vwap"))

        tier2_aligned = ticker in {"SPY", "QQQ"} or (bullish_bias and macro_bullish) or (bearish_bias and macro_bearish)
        hard_extended = bool(row["extension_pct"] > 1.5)
        ema9_penalty_flag = bool(row["dist_ema9_pct"] > 0.8)
        ema21_hard_block = bool(row["dist_ema21_pct"] > 1.5)
        low_liquidity = bool(row["vol_ratio"] < 0.5)
        sufficient_movement = bool(row["atr"] >= min_atr)
        is_choppy = bool(row["net_move_5"] < 0.2)
        timeframe_intraday = bool(row["interval_minutes"] is not None and row["interval_minutes"] < 1440)
        session_conflict = False

        bull_push = bool(index > 0 and bullish_bias and row["close"] > rows[index - 1]["high"] and row["close"] > row["ema9"])
        bear_push = bool(index > 0 and bearish_bias and row["close"] < rows[index - 1]["low"] and row["close"] < row["ema9"])
        bull_push_events.append(bull_push)
        bear_push_events.append(bear_push)

        base_reset_bars = _base_reset_bars(rows, index, bullish_bias=bullish_bias, bearish_bias=bearish_bias)
        leg_count = _leg_count(bull_push_events, bear_push_events, base_reset_bars)
        leg_penalty_flag = leg_count >= 2
        leg_hard_block = leg_count >= 3

        hard_reject = (
            hard_extended
            or ema21_hard_block
            or not any_level_exists
            or low_liquidity
            or not sufficient_movement
            or not tier2_aligned
            or not has_bias
            or not timeframe_intraday
            or session_conflict
        )

        score_raw = 0
        score_penalty = 0
        score = 0
        if not hard_reject:
            if (bullish_bias and macro_bullish) or (bearish_bias and macro_bearish):
                score_raw += 2
            if not is_choppy and ((bullish_bias and row["ema9"] > row["ema21"]) or (bearish_bias and row["ema9"] < row["ema21"])):
                score_raw += 2
            if row["vol_ratio"] >= 1.5:
                score_raw += 2
            if not hard_extended:
                score_raw += 1
            if at_key_level:
                score_raw += 1
            if ema9_penalty_flag:
                score_penalty += 1
            if row["atr_exhaustion"]:
                score_penalty += 1
            if leg_penalty_flag:
                score_penalty += 1
            score = max(0, score_raw - score_penalty)

        breakout_bull = bool(
            index > 0
            and active_level is not None
            and bullish_bias
            and row["close"] > active_level
            and rows[index - 1]["close"] <= active_level
            and row["vol_ratio"] >= 1.5
        )
        breakout_bear = bool(
            index > 0
            and active_level is not None
            and bearish_bias
            and row["close"] < active_level
            and rows[index - 1]["close"] >= active_level
            and row["vol_ratio"] >= 1.5
        )
        breakout_confirmed = breakout_bull or breakout_bear

        retest_hold_bull = bool(
            index > 0
            and active_level is not None
            and bullish_bias
            and rows[index - 1]["close"] > active_level
            and row["low"] <= active_level * (1 + RETEST_TOL)
            and row["close"] > active_level
        )
        retest_hold_bear = bool(
            index > 0
            and active_level is not None
            and bearish_bias
            and rows[index - 1]["close"] < active_level
            and row["high"] >= active_level * (1 - RETEST_TOL)
            and row["close"] < active_level
        )
        confirm_bull = bool(index > 0 and row["close"] > rows[index - 1]["close"])
        confirm_bear = bool(index > 0 and row["close"] < rows[index - 1]["close"])
        reclaim_bull = bool(
            index > 0
            and active_level is not None
            and bullish_bias
            and rows[index - 1]["close"] < active_level
            and row["low"] <= active_level
            and row["close"] > active_level
            and confirm_bull
        )
        reclaim_bear = bool(
            index > 0
            and active_level is not None
            and bearish_bias
            and rows[index - 1]["close"] > active_level
            and row["high"] >= active_level
            and row["close"] < active_level
            and confirm_bear
        )
        reclaim_confirmed = reclaim_bull or reclaim_bear
        retest_confirmed = (retest_hold_bull and confirm_bull) or (retest_hold_bear and confirm_bear)

        setup_type = "NONE"
        if breakout_confirmed:
            setup_type = "BREAKOUT"
        elif reclaim_confirmed:
            setup_type = "RECLAIM"
        elif retest_confirmed:
            setup_type = "PULLBACK"

        open_drive = bool(row["session"] == "OPEN")
        midday = bool(row["session"] == "MIDDAY")
        power_hour = bool(row["session"] == "POWER_HOUR")
        premarket = bool(row["session"] == "PREMARKET")
        late_day = bool(row["session"] == "LATE_DAY")
        postmarket = bool(row["session"] == "POSTMARKET")
        valid_session = open_drive or midday or power_hour

        open_drive_breakout_ok = open_drive and row["vol_ratio"] >= OPEN_DRIVE_VOL_RATIO and breakout_confirmed
        midday_pullback_ok = midday and (retest_confirmed or reclaim_confirmed)
        power_hour_momentum_ok = power_hour and (breakout_confirmed or reclaim_confirmed or retest_confirmed)
        trigger_met = open_drive_breakout_ok or midday_pullback_ok or power_hour_momentum_ok

        ready_conditions = (
            score >= READY_SCORE
            and has_bias
            and tier2_aligned
            and not hard_extended
            and not ema21_hard_block
            and not is_choppy
            and at_key_level
            and active_level is not None
            and not ema9_penalty_flag
            and not row["atr_exhaustion"]
            and not leg_hard_block
            and valid_session
        )

        invalidation_level = locked_level if locked_level is not None else active_level
        invalidation_bias_bull = bullish_bias if locked_bias is None else locked_bias == "bullish"
        invalidation_ref = None
        if invalidation_level is not None:
            invalidation_ref = invalidation_level * (0.999 if invalidation_bias_bull else 1.001)

        locked_structure_break = False
        if state != 0 and locked_bias is not None and invalidation_ref is not None:
            if locked_bias == "bullish":
                locked_structure_break = bool(row["close"] < row["ema21"] or row["close"] < invalidation_ref)
            else:
                locked_structure_break = bool(row["close"] > row["ema21"] or row["close"] > invalidation_ref)

        invalid_now = hard_extended or ema21_hard_block or is_choppy or locked_structure_break

        if state != 0 and invalid_now:
            state = 3

        if state == 0 and not hard_reject and ready_conditions:
            state = 1
            locked_level = active_level
            locked_bias = "bullish" if bullish_bias else "bearish"
            locked_setup_type = "NONE"
            alerted_this_cycle = False
            signals.append(
                ValidationSignal(
                    index=index,
                    timestamp=timestamp,
                    ticker=ticker,
                    timeframe=str(row.get("timeframe") or "intraday"),
                    signal_type="ready",
                    direction=locked_bias,
                    entry_price=float(row["close"]),
                    atr=float(row["atr"]),
                    regime=_string_or_none(row.get("regime")),
                    market_quality=_string_or_none(row.get("market_quality")),
                )
            )

        if state == 1:
            if trigger_met and score >= score_threshold:
                state = 2
                locked_setup_type = setup_type
            elif not ready_conditions or premarket or late_day or postmarket:
                state = 3

        fire_alert = state == 2 and not alerted_this_cycle
        if fire_alert:
            alerted_this_cycle = True
            signal_type = "alert" if not locked_setup_type or locked_setup_type == "NONE" else f"alert_{locked_setup_type.lower()}"
            signals.append(
                ValidationSignal(
                    index=index,
                    timestamp=timestamp,
                    ticker=ticker,
                    timeframe=str(row.get("timeframe") or "intraday"),
                    signal_type=signal_type,
                    direction=str(locked_bias or ("bullish" if bullish_bias else "bearish")),
                    entry_price=float(row["close"]),
                    atr=float(row["atr"]),
                    regime=_string_or_none(row.get("regime")),
                    market_quality=_string_or_none(row.get("market_quality")),
                )
            )

        if state == 2 and invalid_now:
            state = 3

        if state == 3:
            price_reset = locked_level is None or abs(float(row["close"]) - locked_level) / locked_level > 0.005
            if price_reset:
                state = 0
                locked_level = None
                locked_bias = None
                locked_setup_type = None
                alerted_this_cycle = False

        if state == 0:
            alerted_this_cycle = False

    return signals


def _prepare_rows(ticker: str, bars: Sequence[Bar]) -> list[Bar]:
    rows = [dict(bar) for bar in bars]
    interval_minutes = _infer_interval_minutes(rows)
    closes = [float(row["close"]) for row in rows]
    highs = [float(row["high"]) for row in rows]
    lows = [float(row["low"]) for row in rows]
    volumes = [float(row.get("volume", 0.0)) for row in rows]
    ema9 = _ema(closes, 9)
    ema21 = _ema(closes, 21)
    atr = _atr(highs, lows, closes, 14)
    vwap = _vwap(rows)
    vol_avg_60 = _rolling_sma(volumes, max(1, round(60 / interval_minutes))) if interval_minutes else [0.0] * len(rows)

    day_state: dict[str, dict[str, float | bool | None]] = {}
    prev_day_levels = _previous_day_levels(rows)

    for index, row in enumerate(rows):
        dt = _parse_timestamp(str(row["timestamp"]))
        day_key = dt.date().isoformat()
        state = day_state.setdefault(day_key, {"or_high": None, "or_low": None, "or_finalized": False, "pm_high": None, "pm_low": None})
        session = _session_name(dt)
        in_or_window = _minutes(dt) >= 570 and _minutes(dt) < 585
        if in_or_window and not state["or_finalized"]:
            state["or_high"] = float(row["high"]) if state["or_high"] is None else max(float(state["or_high"]), float(row["high"]))
            state["or_low"] = float(row["low"]) if state["or_low"] is None else min(float(state["or_low"]), float(row["low"]))
        if _minutes(dt) >= 585:
            state["or_finalized"] = True
        if session == "PREMARKET":
            state["pm_high"] = float(row["high"]) if state["pm_high"] is None else max(float(state["pm_high"]), float(row["high"]))
            state["pm_low"] = float(row["low"]) if state["pm_low"] is None else min(float(state["pm_low"]), float(row["pm_low"]) if "pm_low" in row else float(row["low"]))

        prev_day_high, prev_day_low = prev_day_levels[index]
        row["ticker"] = ticker
        row["interval_minutes"] = interval_minutes
        row["session"] = session
        row["ema9"] = float(row.get("ema9", ema9[index]))
        row["ema21"] = float(row.get("ema21", ema21[index]))
        row["atr"] = float(row.get("atr", atr[index]))
        row["vwap"] = float(row.get("vwap", vwap[index])) if vwap[index] is not None else None
        row["vol_ratio"] = (volumes[index] / vol_avg_60[index]) if vol_avg_60[index] else 0.0
        row["bar_range"] = float(row["high"]) - float(row["low"])
        row["extension_pct"] = _pct_distance(float(row["close"]), row["vwap"])
        row["dist_ema9_pct"] = _pct_distance(float(row["close"]), row["ema9"])
        row["dist_ema21_pct"] = _pct_distance(float(row["close"]), row["ema21"])
        row["atr_exhaustion"] = bool(row["atr"] > 0 and row["bar_range"] > row["atr"] * 0.8)
        row["net_move_5"] = _net_move_5(closes, index)
        row["or_high"] = _float_or_none(row.get("or_high", state["or_high"]))
        row["or_low"] = _float_or_none(row.get("or_low", state["or_low"]))
        row["pm_high"] = _float_or_none(row.get("pm_high", state["pm_high"]))
        row["pm_low"] = _float_or_none(row.get("pm_low", state["pm_low"]))
        row["prev_day_high"] = prev_day_high
        row["prev_day_low"] = prev_day_low
    return rows


def _previous_day_levels(rows: Sequence[Bar]) -> list[tuple[float | None, float | None]]:
    day_high_low: dict[str, tuple[float, float]] = {}
    for row in rows:
        dt = _parse_timestamp(str(row["timestamp"]))
        day_key = dt.date().isoformat()
        high = float(row["high"])
        low = float(row["low"])
        prior = day_high_low.get(day_key)
        if prior is None:
            day_high_low[day_key] = (high, low)
        else:
            day_high_low[day_key] = (max(prior[0], high), min(prior[1], low))

    ordered_days = sorted(day_high_low)
    prev_lookup: dict[str, tuple[float | None, float | None]] = {}
    previous: tuple[float | None, float | None] = (None, None)
    for day in ordered_days:
        prev_lookup[day] = previous
        previous = day_high_low[day]

    return [prev_lookup[_parse_timestamp(str(row["timestamp"])).date().isoformat()] for row in rows]


def _vwap(rows: Sequence[Bar]) -> list[float | None]:
    output: list[float | None] = []
    current_day = None
    cum_pv = 0.0
    cum_vol = 0.0
    for row in rows:
        dt = _parse_timestamp(str(row["timestamp"]))
        day_key = dt.date().isoformat()
        if day_key != current_day:
            current_day = day_key
            cum_pv = 0.0
            cum_vol = 0.0
        volume = float(row.get("volume", 0.0))
        hlc3 = (float(row["high"]) + float(row["low"]) + float(row["close"])) / 3
        cum_pv += hlc3 * volume
        cum_vol += volume
        output.append((cum_pv / cum_vol) if cum_vol else None)
    return output


def _ema(values: Sequence[float], length: int) -> list[float]:
    alpha = 2 / (length + 1)
    result: list[float] = []
    ema_value = values[0]
    for value in values:
        ema_value = value if not result else (alpha * value) + (1 - alpha) * ema_value
        result.append(ema_value)
    return result


def _atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], length: int) -> list[float]:
    true_ranges: list[float] = []
    for index, (high, low) in enumerate(zip(highs, lows)):
        prev_close = closes[index - 1] if index > 0 else closes[index]
        true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    result: list[float] = []
    running = true_ranges[0]
    for index, tr in enumerate(true_ranges):
        if index == 0:
            running = tr
        elif index < length:
            running = ((running * index) + tr) / (index + 1)
        else:
            running = ((running * (length - 1)) + tr) / length
        result.append(running)
    return result


def _rolling_sma(values: Sequence[float], length: int) -> list[float]:
    result: list[float] = []
    window_sum = 0.0
    for index, value in enumerate(values):
        window_sum += value
        if index >= length:
            window_sum -= values[index - length]
        window_len = min(index + 1, length)
        result.append(window_sum / window_len if window_len else 0.0)
    return result


def _base_reset_bars(rows: Sequence[Bar], index: int, *, bullish_bias: bool, bearish_bias: bool) -> int:
    leg_lookback = 20
    if bullish_bias:
        for offset in range(0, leg_lookback):
            look_index = index - offset
            if look_index < 0:
                break
            if float(rows[look_index]["low"]) <= float(rows[look_index]["ema9"]):
                return offset
        return leg_lookback
    if bearish_bias:
        for offset in range(0, leg_lookback):
            look_index = index - offset
            if look_index < 0:
                break
            if float(rows[look_index]["high"]) >= float(rows[look_index]["ema9"]):
                return offset
        return leg_lookback
    return leg_lookback


def _leg_count(bull_push_events: Sequence[bool], bear_push_events: Sequence[bool], base_reset_bars: int) -> int:
    lookback = min(base_reset_bars, 19)
    current = len(bull_push_events) - 1
    count = 0
    for offset in range(0, 20):
        if offset > lookback:
            continue
        idx = current - offset
        if idx < 0:
            break
        older = idx - 1
        new_bull_leg = bull_push_events[idx] and not (bull_push_events[older] if older >= 0 else False)
        new_bear_leg = bear_push_events[idx] and not (bear_push_events[older] if older >= 0 else False)
        if new_bull_leg or new_bear_leg:
            count += 1
    return count


def _active_level(row: Bar, *, bullish_bias: bool, bearish_bias: bool) -> float | None:
    if bullish_bias:
        return _nearest(float(row["close"]), [_value_or_none(row, key) for key in ("or_high", "pm_high", "prev_day_high", "vwap")])
    if bearish_bias:
        return _nearest(float(row["close"]), [_value_or_none(row, key) for key in ("or_low", "pm_low", "prev_day_low", "vwap")])
    return None


def _nearest(src: float, levels: Sequence[float | None]) -> float | None:
    defined = [level for level in levels if level is not None]
    if not defined:
        return None
    return min(defined, key=lambda level: abs(src - level))


def _near(src: float, level: float | None) -> bool:
    return level is not None and abs(src - level) / src < LEVEL_PROX


def _net_move_5(closes: Sequence[float], index: int) -> float:
    if index < 5 or closes[index - 5] <= 0:
        return 100.0
    return abs(closes[index] - closes[index - 5]) / closes[index - 5] * 100


def _pct_distance(src: float, level: float | None) -> float:
    if level is None or level <= 0:
        return 0.0
    return abs(src - level) / level * 100


def _infer_interval_minutes(rows: Sequence[Bar]) -> int | None:
    if len(rows) < 2:
        timeframe = rows[0].get("timeframe") if rows else None
        return _timeframe_to_minutes(timeframe)
    for index in range(1, len(rows)):
        current = _parse_timestamp(str(rows[index]["timestamp"]))
        previous = _parse_timestamp(str(rows[index - 1]["timestamp"]))
        delta = int((current - previous).total_seconds() // 60)
        if delta > 0:
            return delta
    timeframe = rows[0].get("timeframe") if rows else None
    return _timeframe_to_minutes(timeframe)


def _timeframe_to_minutes(timeframe: object) -> int | None:
    if not isinstance(timeframe, str):
        return None
    value = timeframe.strip().upper()
    if value.endswith("D"):
        return 1440
    if value.endswith("H"):
        return int(value[:-1]) * 60 if value[:-1].isdigit() else None
    return int(value[:-1]) if value.endswith("M") and value[:-1].isdigit() else None


def _session_name(dt: datetime) -> str:
    minute = _minutes(dt)
    if 240 <= minute < 570:
        return "PREMARKET"
    if 570 <= minute < 630:
        return "OPEN"
    if 630 <= minute < 870:
        return "MIDDAY"
    if 870 <= minute < 900:
        return "LATE_DAY"
    if 900 <= minute <= 960:
        return "POWER_HOUR"
    if 960 < minute < 1200:
        return "POSTMARKET"
    return "OFF_HOURS"


def _minutes(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _value_or_none(row: Bar, key: str) -> float | None:
    value = row.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _float_or_none(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _string_or_none(value: object) -> str | None:
    return str(value) if isinstance(value, str) else None
