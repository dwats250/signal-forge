from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reports import build_all


class BuildSiteTests(unittest.TestCase):
    def test_build_site_uses_macro_bundle_entry_point(self) -> None:
        report_data = {
            "date": "2026-04-04",
            "generated_line": "Report Generated at 9:00 AM PDT — 2026-04-04",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            site_dir = Path(tmpdir) / "_site"
            archive_dir = Path(tmpdir) / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_file = archive_dir / "2026-04-04.html"
            archive_file.write_text("<html>archive</html>", encoding="utf-8")
            rendered = Path(tmpdir) / "morning_edge.html"
            rendered.write_text("<html>latest</html>", encoding="utf-8")

            with patch.object(build_all, "SITE_DIR", site_dir):
                with patch.object(build_all.morning_edge, "ARCHIVE_DIR", archive_dir):
                    with patch("reports.build_all.morning_edge.get_macro_bundle", return_value=report_data) as bundle_mock:
                        with patch("reports.build_all.morning_edge.render_html", return_value=rendered):
                            build_all.build_site()

        bundle_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
