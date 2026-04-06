from __future__ import annotations

import argparse

from reports import morning_edge, schedule
from reports.report_lifecycle import vancouver_now


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run or schedule the Daily Premarket Report")
    parser.add_argument("--offline", action="store_true", help="Skip Claude API, use stub narrative")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF rendering")
    parser.add_argument("--schedule", action="store_true", help="Run continuously on the daily schedule (external scheduling preferred)")
    args = parser.parse_args(argv)

    def runner() -> None:
        should_skip, message = schedule.should_skip_premarket_run(vancouver_now().date())
        if should_skip:
            print(message)
            return
        morning_edge.run_report(offline=args.offline, with_pdf=not args.no_pdf)

    if args.schedule:
        schedule.run_scheduler(report_type="premarket", runner=runner)
        return

    runner()


if __name__ == "__main__":
    main()
