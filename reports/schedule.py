from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Callable

from reports.report_lifecycle import vancouver_now
from reports.trading_calendar import is_us_market_holiday, is_us_trading_day

SUNDAY_REPORT_WEEKDAY = 6
SUNDAY_REPORT_HOUR = 17
SUNDAY_REPORT_MINUTE = 0
PREMARKET_REPORT_HOUR = 6
PREMARKET_REPORT_MINUTE = 0


def is_trading_day(now: datetime | None = None) -> bool:
    return is_us_trading_day(vancouver_now(now))


def is_sunday_report_time(now: datetime | None = None) -> bool:
    local_now = vancouver_now(now)
    return (
        local_now.weekday() == SUNDAY_REPORT_WEEKDAY
        and local_now.hour == SUNDAY_REPORT_HOUR
        and local_now.minute == SUNDAY_REPORT_MINUTE
    )


def is_premarket_report_time(now: datetime | None = None) -> bool:
    local_now = vancouver_now(now)
    return (
        is_trading_day(local_now)
        and local_now.hour == PREMARKET_REPORT_HOUR
        and local_now.minute == PREMARKET_REPORT_MINUTE
    )


def next_sunday_report_run(now: datetime | None = None) -> datetime:
    local_now = vancouver_now(now)
    scheduled_today = local_now.replace(
        hour=SUNDAY_REPORT_HOUR,
        minute=SUNDAY_REPORT_MINUTE,
        second=0,
        microsecond=0,
    )
    days_ahead = (SUNDAY_REPORT_WEEKDAY - local_now.weekday()) % 7
    if days_ahead == 0 and local_now <= scheduled_today:
        return scheduled_today
    if days_ahead == 0:
        days_ahead = 7
    return scheduled_today + timedelta(days=days_ahead)


def next_premarket_report_run(now: datetime | None = None) -> datetime:
    local_now = vancouver_now(now)
    candidate = local_now.replace(
        hour=PREMARKET_REPORT_HOUR,
        minute=PREMARKET_REPORT_MINUTE,
        second=0,
        microsecond=0,
    )

    if is_trading_day(local_now) and local_now <= candidate:
        return candidate

    candidate += timedelta(days=1)
    while not is_trading_day(candidate):
        candidate += timedelta(days=1)
    return candidate


def should_skip_premarket_run(local_date: date | None = None) -> tuple[bool, str | None]:
    target_date = vancouver_now().date() if local_date is None else local_date
    if target_date.weekday() >= 5:
        return True, f"[SKIP] Premarket report not generated: weekend ({target_date.isoformat()})"
    if is_us_market_holiday(target_date):
        return True, f"[SKIP] Premarket report not generated: US market holiday ({target_date.isoformat()})"
    return False, None


def next_scheduled_run(report_type: str, now: datetime | None = None) -> datetime:
    if report_type == "sunday":
        return next_sunday_report_run(now)
    if report_type == "premarket":
        return next_premarket_report_run(now)
    raise ValueError(f"unsupported report type: {report_type}")


def run_scheduler(
    *,
    report_type: str,
    runner: Callable[[], None],
    logger: Callable[[str], None] = print,
) -> None:
    while True:
        next_run = next_scheduled_run(report_type)
        logger(f"[WAIT] Next {report_type} run at {next_run.strftime('%Y-%m-%d %H:%M %Z')}")
        sleep_seconds = max(0.0, (next_run - vancouver_now()).total_seconds())
        time.sleep(sleep_seconds)
        runner()
