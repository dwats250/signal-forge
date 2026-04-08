from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reports import morning_edge, run_premarket, sunday_report


class ReportRunnerTests(unittest.TestCase):
    def test_morning_edge_run_report_rotates_live_html_and_pdf(self) -> None:
        counter = {"value": 0}

        def fake_render_html(report_data: dict, out_path: Path | None = None, *, archive_mode: bool = False) -> Path:
            counter["value"] += 1
            out_path.write_text(f"<html>run-{counter['value']}</html>", encoding="utf-8")
            return out_path

        def fake_render_pdf(html_path: Path, out_path: Path | None = None) -> Path:
            out_path.write_text(f"pdf:{html_path.read_text(encoding='utf-8')}", encoding="utf-8")
            return out_path

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_html = root / "output" / "premarket.html"
            live_pdf = root / "output" / "premarket.pdf"
            latest_html = root / "output" / "latest_premarket.html"
            latest_pdf = root / "output" / "latest_premarket.pdf"
            archive_dir = root / "archive" / "daily"
            report_data = {"thesis": "Daily thesis", "date": "2026-04-05"}

            with patch.object(morning_edge, "LIVE_HTML_PATH", live_html):
                with patch.object(morning_edge, "LIVE_PDF_PATH", live_pdf):
                    with patch.object(morning_edge, "LATEST_HTML_PATH", latest_html):
                        with patch.object(morning_edge, "LATEST_PDF_PATH", latest_pdf):
                            with patch.object(morning_edge, "ARCHIVE_DIR", archive_dir):
                                with patch("reports.morning_edge.fetch_market_data", return_value=morning_edge.build_stub_market_data()):
                                    with patch("reports.morning_edge.build_report_data", return_value=report_data):
                                        with patch("reports.morning_edge.render_html", side_effect=fake_render_html):
                                            with patch("reports.morning_edge.render_pdf", side_effect=fake_render_pdf):
                                                morning_edge.run_report(offline=True, with_pdf=True)
                                                morning_edge.run_report(offline=True, with_pdf=True)

            html_archives = sorted(archive_dir.glob("premarket_*.html"))
            pdf_archives = sorted(archive_dir.glob("premarket_*.pdf"))

            self.assertEqual(live_html.read_text(encoding="utf-8"), "<html>run-2</html>")
            self.assertEqual(live_pdf.read_text(encoding="utf-8"), "pdf:<html>run-2</html>")
            self.assertEqual(latest_html.read_text(encoding="utf-8"), "<html>run-2</html>")
            self.assertEqual(latest_pdf.read_text(encoding="utf-8"), "pdf:<html>run-2</html>")
            self.assertEqual(len(html_archives), 1)
            self.assertEqual(len(pdf_archives), 1)

    def test_morning_edge_run_report_preserves_live_output_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_html = root / "output" / "premarket.html"
            latest_html = root / "output" / "latest_premarket.html"
            live_html.parent.mkdir(parents=True, exist_ok=True)
            live_html.write_text("<html>prior</html>", encoding="utf-8")
            latest_html.write_text("<html>prior-latest</html>", encoding="utf-8")
            archive_dir = root / "archive" / "daily"

            with patch.object(morning_edge, "LIVE_HTML_PATH", live_html):
                with patch.object(morning_edge, "LATEST_HTML_PATH", latest_html):
                    with patch.object(morning_edge, "ARCHIVE_DIR", archive_dir):
                        with patch(
                            "reports.morning_edge.fetch_market_data",
                            return_value=morning_edge.build_stub_market_data(),
                        ):
                            with patch(
                                "reports.morning_edge.build_report_data",
                                return_value={"thesis": "Daily thesis"},
                            ):
                                with patch(
                                    "reports.morning_edge.render_html",
                                    side_effect=RuntimeError("boom"),
                                ):
                                    result = morning_edge.run_report(offline=True, with_pdf=False)

            self.assertEqual(live_html.read_text(encoding="utf-8"), "<html>prior</html>")
            self.assertEqual(latest_html.read_text(encoding="utf-8"), "<html>prior-latest</html>")
            self.assertFalse(archive_dir.exists())
            self.assertIn("morning_edge.html_render", result["_failed_stages"])

    def test_sunday_run_report_rotates_live_html_and_pdf(self) -> None:
        counter = {"value": 0}

        def fake_render_html(report_data: dict, out_path: Path | None = None) -> Path:
            counter["value"] += 1
            out_path.write_text(f"<html>sunday-{counter['value']}</html>", encoding="utf-8")
            return out_path

        def fake_render_pdf(html_path: Path, out_path: Path | None = None) -> Path:
            out_path.write_text(f"pdf:{html_path.read_text(encoding='utf-8')}", encoding="utf-8")
            return out_path

        report_data = {
            "regime": "MIXED",
            "quality": "MIXED",
            "posture": "TRADE SELECTIVELY",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_html = root / "output" / "sunday_report.html"
            live_pdf = root / "output" / "sunday_report.pdf"
            latest_html = root / "output" / "latest_sunday.html"
            latest_pdf = root / "output" / "latest_sunday.pdf"
            archive_dir = root / "archive" / "sunday"

            with patch.object(sunday_report, "LIVE_HTML_PATH", live_html):
                with patch.object(sunday_report, "LIVE_PDF_PATH", live_pdf):
                    with patch.object(sunday_report, "LATEST_HTML_PATH", latest_html):
                        with patch.object(sunday_report, "LATEST_PDF_PATH", latest_pdf):
                            with patch.object(sunday_report, "ARCHIVE_DIR", archive_dir):
                                with patch("reports.sunday_report.fetch_market_data", return_value={}):
                                    with patch("reports.sunday_report._week_label", return_value=("April 6, 2026", "Apr 6 - Apr 10, 2026")):
                                        with patch("reports.sunday_report._stub_narrative", return_value={}):
                                            with patch("reports.sunday_report.build_report_data", return_value=report_data):
                                                with patch("reports.sunday_report.render_html", side_effect=fake_render_html):
                                                    with patch("reports.sunday_report.render_pdf", side_effect=fake_render_pdf):
                                                        sunday_report.run_report(offline=True, with_pdf=True)
                                                        sunday_report.run_report(offline=True, with_pdf=True)

            html_archives = sorted(archive_dir.glob("sunday_report_*.html"))
            pdf_archives = sorted(archive_dir.glob("sunday_report_*.pdf"))

            self.assertEqual(live_html.read_text(encoding="utf-8"), "<html>sunday-2</html>")
            self.assertEqual(live_pdf.read_text(encoding="utf-8"), "pdf:<html>sunday-2</html>")
            self.assertEqual(latest_html.read_text(encoding="utf-8"), "<html>sunday-2</html>")
            self.assertEqual(latest_pdf.read_text(encoding="utf-8"), "pdf:<html>sunday-2</html>")
            self.assertEqual(len(html_archives), 1)
            self.assertEqual(len(pdf_archives), 1)

    def test_run_premarket_skips_generation_on_holiday(self) -> None:
        with patch("reports.run_premarket.schedule.should_skip_premarket_run", return_value=(True, "[SKIP] Premarket report not generated: US market holiday (2026-12-25)")):
            with patch("reports.run_premarket.morning_edge.run_report") as run_mock:
                run_premarket.main([])

        run_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
