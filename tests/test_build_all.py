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
            "state_summary": {
                "market_posture": "Mixed",
                "market_quality": "Fragile",
            },
            "no_setups": True,
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
            market_cache = Path(tmpdir) / "market_data.latest.json"
            sunday_cache = Path(tmpdir) / "sunday_market.latest.json"
            market_cache.write_text(
                """{
  "data": {
    "SPY": {"day_chg": 0.2, "price": 1},
    "QQQ": {"day_chg": 0.4, "price": 1},
    "DXY": {"day_chg": 0.0, "price": 100.0},
    "US10Y": {"day_chg": -0.6, "price": 4.3},
    "VIX": {"day_chg": -2.0, "price": 24.0},
    "WTI": {"day_chg": 0.8, "price": 112.0},
    "GOLD": {"day_chg": -0.4, "price": 4600.0},
    "BTC": {"day_chg": 1.8, "price": 69000.0}
  }
}""",
                encoding="utf-8",
            )
            sunday_cache.write_text(
                """{
  "data": {
    "WTI": {"week_chg": 10.0}
  }
}""",
                encoding="utf-8",
            )

            with patch.object(build_all, "SITE_DIR", site_dir):
                with patch.object(build_all.morning_edge, "ARCHIVE_DIR", archive_dir):
                    with patch.object(build_all.morning_edge, "LIVE_HTML_PATH", rendered):
                        with patch.object(build_all.morning_edge, "MARKET_CACHE_PATH", market_cache):
                            with patch.object(build_all.morning_edge, "LATEST_HTML_PATH", latest_premarket_html):
                                with patch.object(build_all.morning_edge, "LATEST_PDF_PATH", latest_premarket_pdf):
                                    with patch.object(build_all.sunday_report, "MARKET_CACHE_PATH", sunday_cache):
                                        with patch.object(build_all.sunday_report, "LATEST_HTML_PATH", latest_sunday_html):
                                            with patch.object(build_all.sunday_report, "LATEST_PDF_PATH", latest_sunday_pdf):
                                                with patch("reports.build_all.morning_edge.run_report", return_value=report_data) as run_mock:
                                                    build_all.build_site()
            run_mock.assert_called_once()
            self.assertTrue((site_dir / "latest_premarket.html").exists())
            self.assertTrue((site_dir / "latest_premarket.pdf").exists())
            self.assertTrue((site_dir / "latest_sunday.html").exists())
            self.assertTrue((site_dir / "latest_sunday.pdf").exists())
            index_html = (site_dir / "index.html").read_text(encoding="utf-8")
            self.assertIn("Risk</div>", index_html)
            self.assertIn("Driver</div>", index_html)
            self.assertIn("Confidence</div>", index_html)
            self.assertIn("Trigger</div>", index_html)
            self.assertIn("Posture</div>", index_html)
            self.assertIn("Focus</div>", index_html)
            self.assertIn("What Matters Now", index_html)
            self.assertIn("Key Signals Strip", index_html)
            self.assertIn('href="latest_sunday.html"', index_html)
            self.assertIn('href="latest_premarket.pdf"', index_html)
            self.assertLess(index_html.index("Risk</div>"), index_html.index("Latest Reports"))
            self.assertLess(index_html.index("Trigger</div>"), index_html.index("Posture</div>"))


if __name__ == "__main__":
    unittest.main()
