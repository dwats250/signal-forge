from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reports import sunday_report


class SundayNarrativeHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.market_data = sunday_report.build_stub_market_data()

    def test_valid_narrative_json_parses_normally(self) -> None:
        payload = sunday_report._stub_narrative(self.market_data)
        result = sunday_report._parse_sunday_narrative(json.dumps(payload))
        validation = sunday_report._validate_sunday_narrative_payload(payload)

        self.assertTrue(result.ok)
        self.assertEqual(result.payload["regime"], payload["regime"])
        self.assertTrue(validation.ok)

    def test_empty_response_triggers_safe_fallback(self) -> None:
        class _FakeContent:
            text = ""

        class _FakeResponse:
            content = [_FakeContent()]

        class _FakeMessages:
            @staticmethod
            def create(**_: object) -> _FakeResponse:
                return _FakeResponse()

        class _FakeClient:
            def __init__(self, api_key: str) -> None:
                self.messages = _FakeMessages()

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "sunday_narrative_failure.latest.json"
            with patch.object(sunday_report, "NARRATIVE_FAILURE_ARTIFACT_PATH", artifact_path):
                with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
                    with patch("reports.sunday_report.anthropic.Anthropic", _FakeClient):
                        with patch("reports.sunday_report.append_report_log") as log_mock:
                            outcome = sunday_report._resolve_narrative(self.market_data, "April 13, 2026")
                            self.assertTrue(artifact_path.exists())
                            logged = " ".join(str(call.args) for call in log_mock.call_args_list)
                            self.assertIn("recovered", logged)

        self.assertTrue(outcome.used_fallback)
        self.assertEqual(outcome.reason, "empty_response")
        self.assertIn("Fallback narrative in effect", outcome.narrative["regime_bullets"][0])

    def test_malformed_json_triggers_safe_fallback(self) -> None:
        result = sunday_report._parse_sunday_narrative('{"regime":"MIXED"')
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "malformed_json")

    def test_markdown_wrapped_json_is_extracted(self) -> None:
        payload = sunday_report._stub_narrative(self.market_data)
        wrapped = f"Here is the report:\n```json\n{json.dumps(payload)}\n```"

        result = sunday_report._parse_sunday_narrative(wrapped)

        self.assertTrue(result.ok)
        self.assertEqual(result.parse_mode, "markdown_fence")

    def test_missing_required_field_triggers_validation_failure_and_fallback(self) -> None:
        payload = sunday_report._stub_narrative(self.market_data)
        payload.pop("regime")

        validation = sunday_report._validate_sunday_narrative_payload(payload)

        self.assertFalse(validation.ok)
        self.assertEqual(validation.reason, "missing_required_field")

    def test_wrong_field_types_trigger_validation_failure_and_fallback(self) -> None:
        payload = sunday_report._stub_narrative(self.market_data)
        payload["themes"] = "not-a-list"

        validation = sunday_report._validate_sunday_narrative_payload(payload)

        self.assertFalse(validation.ok)
        self.assertEqual(validation.reason, "invalid_field_type")

    def test_run_report_marks_recovered_narrative_non_fatal(self) -> None:
        class _FakeContent:
            text = ""

        class _FakeResponse:
            content = [_FakeContent()]

        class _FakeMessages:
            @staticmethod
            def create(**_: object) -> _FakeResponse:
                return _FakeResponse()

        class _FakeClient:
            def __init__(self, api_key: str) -> None:
                self.messages = _FakeMessages()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_html = root / "output" / "sunday_report.html"
            latest_html = root / "output" / "latest_sunday.html"
            archive_dir = root / "archive" / "sunday"
            artifact_path = root / "output" / "sunday_narrative_failure.latest.json"
            with patch.object(sunday_report, "LIVE_HTML_PATH", live_html):
                with patch.object(sunday_report, "LATEST_HTML_PATH", latest_html):
                    with patch.object(sunday_report, "ARCHIVE_DIR", archive_dir):
                        with patch.object(sunday_report, "NARRATIVE_FAILURE_ARTIFACT_PATH", artifact_path):
                            with patch("reports.sunday_report.fetch_market_data", return_value=self.market_data):
                                with patch("reports.sunday_report.render_pdf", return_value=root / "output" / "sunday_report.pdf"):
                                    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
                                        with patch("reports.sunday_report.anthropic.Anthropic", _FakeClient):
                                            result = sunday_report.run_report(offline=False, with_pdf=False)
                                            self.assertTrue(live_html.exists())
                                            self.assertTrue(artifact_path.exists())

        self.assertEqual(result.get("_failed_stages"), [])


if __name__ == "__main__":
    unittest.main()
