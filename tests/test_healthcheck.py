from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from reports.morning_healthcheck import (
    aggregate_setup_outcomes,
    build_cli_summary,
    build_morning_healthcheck_summary,
    build_notification_message,
    build_status_file,
)


class MorningHealthcheckTests(unittest.TestCase):
    def test_aggregate_setup_outcomes_counts_watchlist_and_blocks(self) -> None:
        entries = [
            {"setup_outcome": "READY"},
            {"setup_outcome": "WATCHLIST", "dominant_reason": "MIXED_REGIME"},
            {"setup_outcome": "BLOCKED", "dominant_reason": "FAILED_RR"},
            {"setup_outcome": "BLOCKED", "dominant_reason": "FAILED_RR"},
        ]

        summary = aggregate_setup_outcomes(entries)

        self.assertEqual(summary["ready"], 1)
        self.assertEqual(summary["watchlist"], 1)
        self.assertEqual(summary["blocked"], 2)
        self.assertEqual(summary["block_reasons"]["FAILED_RR"], 2)
        self.assertEqual(summary["block_reasons"]["MIXED_REGIME"], 1)

    def test_build_summary_reads_execution_log_and_formats_outputs(self) -> None:
        report_data = {
            "confidence_score": 78,
            "market_data": {
                "_meta": {
                    "confidence_score": 78,
                    "fallback_symbols": ["DXY", "US10Y"],
                    "core_macro_health": "degraded",
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            decision_log = Path(tmpdir) / "decision_log.jsonl"
            decision_log.write_text(
                "\n".join(
                    [
                        '{"setup_outcome":"WATCHLIST","execution_mode":"SELECTIVE","dominant_reason":"MIXED_REGIME"}',
                        '{"setup_outcome":"BLOCKED","execution_mode":"NO_TRADE","dominant_reason":"FAILED_RR"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = build_morning_healthcheck_summary(
                stage_statuses={
                    "sunday_report": "success",
                    "morning_edge": "success",
                    "dashboard": "success",
                },
                report_data=report_data,
                decision_log_path=decision_log,
            )

        self.assertEqual(summary["build_status"], "SUCCESS")
        self.assertEqual(summary["execution_mode"], "NO_TRADE")
        self.assertEqual(summary["top_block_reason"], "MIXED_REGIME")
        self.assertTrue(summary["fallback_used"])
        self.assertIn("EXECUTION MODE: NO_TRADE", build_cli_summary(summary))
        self.assertIn("CORE_MACRO=DEGRADED", build_status_file(summary))
        self.assertIn("Fallback: DXY,US10Y", build_notification_message(summary))


if __name__ == "__main__":
    unittest.main()
