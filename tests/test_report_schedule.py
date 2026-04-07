from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from reports import schedule
from reports.report_lifecycle import REPORT_TIMEZONE


class ReportScheduleTests(unittest.TestCase):
    def test_is_trading_day_uses_weekday_fallback(self) -> None:
        self.assertTrue(schedule.is_trading_day(datetime(2026, 4, 6, 6, 0, tzinfo=REPORT_TIMEZONE)))
        self.assertFalse(schedule.is_trading_day(datetime(2026, 4, 4, 6, 0, tzinfo=REPORT_TIMEZONE)))
        self.assertFalse(schedule.is_trading_day(datetime(2026, 12, 25, 6, 0, tzinfo=REPORT_TIMEZONE)))

    def test_next_premarket_report_run_rolls_to_next_weekday(self) -> None:
        now = datetime(2026, 4, 3, 7, 0, tzinfo=REPORT_TIMEZONE)

        next_run = schedule.next_premarket_report_run(now)

        self.assertEqual(next_run, datetime(2026, 4, 6, 6, 0, tzinfo=REPORT_TIMEZONE))

    def test_next_premarket_report_run_skips_market_holiday(self) -> None:
        now = datetime(2026, 12, 24, 7, 0, tzinfo=REPORT_TIMEZONE)

        next_run = schedule.next_premarket_report_run(now)

        self.assertEqual(next_run, datetime(2026, 12, 28, 6, 0, tzinfo=REPORT_TIMEZONE))

    def test_next_sunday_report_run_stays_same_day_before_deadline(self) -> None:
        now = datetime(2026, 4, 5, 16, 0, tzinfo=REPORT_TIMEZONE)

        next_run = schedule.next_sunday_report_run(now)

        self.assertEqual(next_run, datetime(2026, 4, 5, 17, 0, tzinfo=REPORT_TIMEZONE))

    def test_next_scheduled_run_routes_by_report_type(self) -> None:
        now = datetime(2026, 4, 5, 18, 0, tzinfo=REPORT_TIMEZONE)

        sunday_next = schedule.next_scheduled_run("sunday", now)
        premarket_next = schedule.next_scheduled_run("premarket", now)

        self.assertEqual(sunday_next, datetime(2026, 4, 12, 17, 0, tzinfo=REPORT_TIMEZONE))
        self.assertEqual(premarket_next, datetime(2026, 4, 6, 6, 0, tzinfo=REPORT_TIMEZONE))

    def test_schedule_checks_convert_utc_into_vancouver_time(self) -> None:
        sunday_utc = datetime(2026, 4, 6, 0, 0, tzinfo=timezone.utc)
        premarket_utc = datetime(2026, 4, 6, 13, 0, tzinfo=timezone.utc)

        self.assertTrue(schedule.is_sunday_report_time(sunday_utc))
        self.assertTrue(schedule.is_premarket_report_time(premarket_utc))

    def test_should_skip_premarket_run_for_holiday(self) -> None:
        should_skip, message = schedule.should_skip_premarket_run(date(2026, 12, 25))

        self.assertTrue(should_skip)
        self.assertEqual(message, "[SKIP] Premarket report not generated: US market holiday (2026-12-25)")


if __name__ == "__main__":
    unittest.main()
