from __future__ import annotations

from datetime import date, datetime, timedelta

from reports.report_lifecycle import vancouver_now


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    current = date(year, month, 1)
    while current.weekday() != weekday:
        current += timedelta(days=1)
    current += timedelta(days=7 * (n - 1))
    return current


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        current = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        current = date(year, month + 1, 1) - timedelta(days=1)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current


def _easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _observed_fixed_holiday(year: int, month: int, day: int) -> date:
    holiday = date(year, month, day)
    if holiday.weekday() == 5:
        return holiday - timedelta(days=1)
    if holiday.weekday() == 6:
        return holiday + timedelta(days=1)
    return holiday


def us_market_holidays(year: int) -> set[date]:
    return {
        _observed_fixed_holiday(year, 1, 1),
        _nth_weekday(year, 1, 0, 3),   # MLK Day
        _nth_weekday(year, 2, 0, 3),   # Presidents Day
        _easter_sunday(year) - timedelta(days=2),  # Good Friday
        _last_weekday(year, 5, 0),     # Memorial Day
        _observed_fixed_holiday(year, 6, 19),  # Juneteenth
        _observed_fixed_holiday(year, 7, 4),   # Independence Day
        _nth_weekday(year, 9, 0, 1),   # Labor Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
        _observed_fixed_holiday(year, 12, 25),  # Christmas
    }


def is_us_market_holiday(value: date | datetime) -> bool:
    local_date = value.date() if isinstance(value, datetime) else value
    return local_date in us_market_holidays(local_date.year)


def is_us_trading_day(value: date | datetime | None = None) -> bool:
    if value is None:
        local_date = vancouver_now().date()
    elif isinstance(value, datetime):
        local_date = vancouver_now(value).date()
    else:
        local_date = value
    return local_date.weekday() < 5 and not is_us_market_holiday(local_date)
