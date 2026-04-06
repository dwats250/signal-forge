from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reports import build_all


class BuildSiteTests(unittest.TestCase):
    def test_build_site_uses_report_runner_entry_point(self) -> None:
        report_data = {
            "date": "2026-04-04",
            "generated_line": "Report Generated at 9:00 AM PDT — 2026-04-04",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            site_dir = Path(tmpdir) / "_site"
            archive_dir = Path(tmpdir) / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_file = archive_dir / "premarket_2026-04-05.html"
            archive_file.write_text("<html>archive</html>", encoding="utf-8")
            rendered = Path(tmpdir) / "premarket.html"
            rendered.write_text(
                '<html><body><a href="latest_sunday.html">Sunday</a><a href="latest_premarket.pdf">Premarket PDF</a></body></html>',
                encoding="utf-8",
            )
            latest_premarket_html = Path(tmpdir) / "latest_premarket.html"
            latest_premarket_pdf = Path(tmpdir) / "latest_premarket.pdf"
            latest_sunday_html = Path(tmpdir) / "latest_sunday.html"
            latest_sunday_pdf = Path(tmpdir) / "latest_sunday.pdf"
            latest_premarket_html.write_text("<html>premarket</html>", encoding="utf-8")
            latest_premarket_pdf.write_bytes(b"%PDF-premarket")
            latest_sunday_html.write_text("<html>sunday</html>", encoding="utf-8")
            latest_sunday_pdf.write_bytes(b"%PDF-sunday")

            with patch.object(build_all, "SITE_DIR", site_dir):
                with patch.object(build_all.morning_edge, "ARCHIVE_DIR", archive_dir):
                    with patch.object(build_all.morning_edge, "LIVE_HTML_PATH", rendered):
                        with patch.object(build_all.morning_edge, "LATEST_HTML_PATH", latest_premarket_html):
                            with patch.object(build_all.morning_edge, "LATEST_PDF_PATH", latest_premarket_pdf):
                                with patch.object(build_all.sunday_report, "LATEST_HTML_PATH", latest_sunday_html):
                                    with patch.object(build_all.sunday_report, "LATEST_PDF_PATH", latest_sunday_pdf):
                                        with patch("reports.build_all.morning_edge.run_report", return_value=report_data) as run_mock:
                                            build_all.build_site()
            run_mock.assert_called_once()
            self.assertTrue((site_dir / "latest_premarket.html").exists())
            self.assertTrue((site_dir / "latest_premarket.pdf").exists())
            self.assertTrue((site_dir / "latest_sunday.html").exists())
            self.assertTrue((site_dir / "latest_sunday.pdf").exists())
            self.assertIn('href="latest_sunday.html"', (site_dir / "index.html").read_text(encoding="utf-8"))
            self.assertIn('href="latest_premarket.pdf"', (site_dir / "index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
