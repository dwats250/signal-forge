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
            self.assertEqual(result["pipeline_mode"], "full")

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
        snapshot["_meta"]["critical_missing_groups"] = ["volatility"]
        snapshot["_meta"]["mode"] = "unavailable"
        snapshot["_meta"]["decision"] = "skip"
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            with patch.object(run_live_pipeline, "LOG_DIR", log_dir), patch.object(
                run_live_pipeline, "AUDIT_LOG_PATH", log_dir / "live_pipeline_audit.jsonl"
            ), patch.object(run_live_pipeline, "DECISION_LOG_PATH", log_dir / "decision_log.jsonl"):
                result = run_live_pipeline.run_live_pipeline(snapshot=snapshot)

            self.assertEqual(result["status"], "skipped")
            self.assertFalse((log_dir / "decision_log.jsonl").exists())
            self.assertEqual(result["pipeline_mode"], "unavailable")

    def test_run_live_pipeline_proceeds_in_degraded_mode_when_optional_groups_are_missing(self) -> None:
        snapshot = self._snapshot()
        snapshot["DXY"] = {"day_chg": None, "price": None}
        snapshot["US10Y"] = {"day_chg": None, "price": None}
        snapshot["_meta"]["missing_groups"] = ["fx", "rates"]
        snapshot["_meta"]["mode"] = "degraded"
        snapshot["_meta"]["decision"] = "proceed"

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            with patch.object(run_live_pipeline, "LOG_DIR", log_dir), patch.object(
                run_live_pipeline, "AUDIT_LOG_PATH", log_dir / "live_pipeline_audit.jsonl"
            ), patch.object(run_live_pipeline, "DECISION_LOG_PATH", log_dir / "decision_log.jsonl"):
                result = run_live_pipeline.run_live_pipeline(snapshot=snapshot)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["pipeline_mode"], "degraded")
        self.assertEqual(result["missing_groups"], ["fx", "rates"])

    def test_run_live_pipeline_skips_cleanly_on_fetch_failure(self) -> None:
        with patch.object(
            run_live_pipeline,
            "collect_market_snapshot",
            return_value=run_live_pipeline.SnapshotFetchResult(
                snapshot={"_meta": {"sources": ["unavailable"]}},
                diagnostics=[
                    {
                        "provider": "fmp",
                        "group": "equities",
                        "status": "failed",
                        "error_type": "HTTPError",
                        "error": "HTTP 401",
                    }
                ],
                missing_tickers=["SPY", "QQQ", "IWM", "VIX"],
                missing_groups=["equities", "volatility"],
                partial_groups=[],
                critical_missing_groups=["equities", "volatility"],
                sources=["unavailable"],
                mode="unavailable",
                decision="skip",
                fatal=True,
            ),
        ):
            result = run_live_pipeline.run_live_pipeline()

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["pipeline_mode"], "unavailable")
        self.assertEqual(result["decision"], "skip")
        self.assertEqual(result["diagnostics"][0]["error"], "HTTP 401")

    def test_run_live_pipeline_skips_cleanly_on_snapshot_shape_failure(self) -> None:
        with patch.object(
            run_live_pipeline,
            "collect_market_snapshot",
            return_value=run_live_pipeline.SnapshotFetchResult(
                snapshot=["SPY", "QQQ"],
                diagnostics=[],
                missing_tickers=[],
                missing_groups=[],
                partial_groups=[],
                critical_missing_groups=[],
                sources=["fmp"],
                mode="full",
                decision="proceed",
                fatal=False,
            ),
        ):
            result = run_live_pipeline.run_live_pipeline()

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "DATA SHAPE FAILED — EXPECTED DICT SNAPSHOT")
        self.assertEqual(result["diagnostics"][0]["error_type"], "DataShapeError")

    def test_main_prints_minimal_success_output(self) -> None:
        with patch.object(
            run_live_pipeline,
            "run_live_pipeline",
            return_value={
                "status": "ok",
                "pipeline_mode": "full",
                "decision": "proceed",
                "missing_groups": [],
                "partial_groups": [],
                "diagnostics": [],
                "regime": "bullish",
                "ready_count": 1,
                "blocked_count": 0,
            },
        ):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                run_live_pipeline.main([])

        self.assertEqual(
            stdout.getvalue(),
            "[pipeline] mode=full render=proceed missing_groups=none partial_groups=none\nREGIME: bullish\nTRADES: READY=1 BLOCKED=0\n",
        )

    def test_main_prints_skip_message_with_diagnostics(self) -> None:
        with patch.object(
            run_live_pipeline,
            "run_live_pipeline",
            return_value={
                "status": "skipped",
                "reason": "minimum viable dataset unavailable",
                "pipeline_mode": "unavailable",
                "decision": "skip",
                "missing_groups": ["equities", "volatility"],
                "partial_groups": [],
                "diagnostics": [
                    {
                        "provider": "fmp",
                        "group": "equities",
                        "status": "failed",
                        "error_type": "HTTPError",
                        "error": "HTTP 401",
                        "fatal": True,
                    }
                ],
            },
        ):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                run_live_pipeline.main([])

        self.assertEqual(
            stdout.getvalue(),
            "[fetch] provider=fmp group=equities status=failed exception=HTTPError error=HTTP 401 fatal=yes\n"
            "[pipeline] mode=unavailable render=skip missing_groups=equities,volatility partial_groups=none\n"
            "DATA FETCH FAILED — SKIPPING RUN (minimum viable dataset unavailable)\n",
        )

    def test_main_preflight_prints_status_without_running_pipeline(self) -> None:
        with patch.object(
            run_live_pipeline,
            "run_preflight",
            return_value={
                "status": "ok",
                "pipeline_mode": "degraded",
                "decision": "proceed",
                "missing_groups": ["fx"],
                "partial_groups": ["energy"],
                "diagnostics": [],
            },
        ):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                run_live_pipeline.main(["--preflight"])

        self.assertEqual(
            stdout.getvalue(),
            "[pipeline] mode=degraded render=proceed missing_groups=fx partial_groups=energy\nPREFLIGHT OK\n",
        )


if __name__ == "__main__":
    unittest.main()
