from __future__ import annotations

import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import run_live_pipeline


class RunLivePipelineTests(unittest.TestCase):
    def _snapshot(self) -> dict[str, dict[str, object]]:
        return {
            "SPY": {"day_chg": 1.2, "price": 101.0},
            "QQQ": {"day_chg": 0.9, "price": 202.0},
            "IWM": {"day_chg": 0.4, "price": 51.0},
            "DXY": {"day_chg": -0.2, "price": 30.0},
            "VIX": {"day_chg": -1.0, "price": 17.0},
            "US10Y": {"day_chg": 4.0, "price": 90.0},
            "GOLD": {"day_chg": 0.3, "price": 180.0},
            "OIL": {"day_chg": 0.5, "price": 70.0},
            "XLE": {"day_chg": 0.7, "price": 80.0},
            "_meta": {"fetched_at": "2026-04-05T00:00:00+00:00", "sources": ["fmp"], "missing_tickers": []},
        }

    def test_run_live_pipeline_logs_full_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            with patch.object(run_live_pipeline, "LOG_DIR", log_dir), patch.object(
                run_live_pipeline, "AUDIT_LOG_PATH", log_dir / "live_pipeline_audit.jsonl"
            ), patch.object(run_live_pipeline, "DECISION_LOG_PATH", log_dir / "decision_log.jsonl"):
                result = run_live_pipeline.run_live_pipeline(snapshot=self._snapshot())

            self.assertEqual(result["status"], "ok")
            lines = (log_dir / "decision_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            self.assertEqual(payload["policy_decision"], "pass")
            self.assertEqual(payload["execution_status"], "ready")
            self.assertFalse(payload["sized"])
            self.assertEqual(result["regime"], payload["regime"])
            self.assertEqual(result["ready_count"], 1)
            self.assertEqual(result["blocked_count"], 0)

    def test_run_live_pipeline_appends_one_record_per_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            with patch.object(run_live_pipeline, "LOG_DIR", log_dir), patch.object(
                run_live_pipeline, "AUDIT_LOG_PATH", log_dir / "live_pipeline_audit.jsonl"
            ), patch.object(run_live_pipeline, "DECISION_LOG_PATH", log_dir / "decision_log.jsonl"):
                run_live_pipeline.run_live_pipeline(snapshot=self._snapshot())
                run_live_pipeline.run_live_pipeline(snapshot=self._snapshot())

            lines = (log_dir / "decision_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)

    def test_run_live_pipeline_skips_when_snapshot_has_missing_data(self) -> None:
        snapshot = self._snapshot()
        snapshot["VIX"] = {"day_chg": None, "price": None}
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            with patch.object(run_live_pipeline, "LOG_DIR", log_dir), patch.object(
                run_live_pipeline, "AUDIT_LOG_PATH", log_dir / "live_pipeline_audit.jsonl"
            ), patch.object(run_live_pipeline, "DECISION_LOG_PATH", log_dir / "decision_log.jsonl"):
                result = run_live_pipeline.run_live_pipeline(snapshot=snapshot)

            self.assertEqual(result["status"], "skipped")
            self.assertFalse((log_dir / "decision_log.jsonl").exists())

    def test_run_live_pipeline_skips_cleanly_on_fetch_failure(self) -> None:
        with patch.object(run_live_pipeline, "fetch_market_snapshot", side_effect=run_live_pipeline.LiveDataUnavailableError("fmp down")):
            result = run_live_pipeline.run_live_pipeline()

        self.assertEqual(result, {"status": "skipped", "reason": "fmp down"})

    def test_main_prints_minimal_success_output(self) -> None:
        with patch.object(run_live_pipeline, "run_live_pipeline", return_value={"status": "ok", "regime": "bullish", "ready_count": 1, "blocked_count": 0}):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                run_live_pipeline.main()

        self.assertEqual(stdout.getvalue(), "REGIME: bullish\nTRADES: READY=1 BLOCKED=0\n")

    def test_main_prints_skip_message(self) -> None:
        with patch.object(run_live_pipeline, "run_live_pipeline", return_value={"status": "skipped", "reason": "fmp down"}):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                run_live_pipeline.main()

        self.assertEqual(stdout.getvalue(), "DATA FETCH FAILED — SKIPPING RUN\n")


if __name__ == "__main__":
    unittest.main()
