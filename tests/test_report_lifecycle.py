from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from reports import report_lifecycle


class ReportLifecycleTests(unittest.TestCase):
    def test_resolve_archive_path_uses_vancouver_local_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_dir = Path(tmpdir) / "archive"
            now = datetime(2026, 4, 6, 1, 30, tzinfo=timezone.utc)

            archive_path = report_lifecycle.resolve_archive_path(
                archive_dir,
                "premarket",
                ".html",
                now=now,
            )

        self.assertEqual(archive_path.name, "premarket_2026-04-05.html")

    def test_resolve_archive_path_adds_time_suffix_on_same_day_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_dir = Path(tmpdir) / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            (archive_dir / "premarket_2026-04-05.html").write_text("prior", encoding="utf-8")
            now = datetime(2026, 4, 5, 6, 30, tzinfo=report_lifecycle.REPORT_TIMEZONE)

            archive_path = report_lifecycle.resolve_archive_path(
                archive_dir,
                "premarket",
                ".html",
                now=now,
            )

        self.assertEqual(archive_path.name, "premarket_2026-04-05_0630.html")

    def test_promote_report_artifact_archives_prior_live_before_promoting_new(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_path = root / "output" / "premarket.html"
            latest_path = root / "output" / "latest_premarket.html"
            archive_dir = root / "archive" / "daily"
            live_path.parent.mkdir(parents=True, exist_ok=True)
            live_path.write_text("old-live", encoding="utf-8")
            temp_path = root / "tmp" / "premarket.html"
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text("new-live", encoding="utf-8")
            logs: list[str] = []

            promoted_path, archive_path = report_lifecycle.promote_report_artifact(
                report_label="Daily Premarket Report HTML",
                live_path=live_path,
                archive_dir=archive_dir,
                archive_prefix="premarket",
                temp_path=temp_path,
                latest_pointer_path=latest_path,
                logger=logs.append,
                now=datetime(2026, 4, 5, 6, 30, tzinfo=report_lifecycle.REPORT_TIMEZONE),
            )
            promoted_text = promoted_path.read_text(encoding="utf-8")
            archived_text = archive_path.read_text(encoding="utf-8")
            latest_text = latest_path.read_text(encoding="utf-8")
            temp_exists = temp_path.exists()

        self.assertEqual(promoted_text, "new-live")
        self.assertEqual(archived_text, "old-live")
        self.assertEqual(latest_text, "new-live")
        self.assertFalse(temp_exists)
        self.assertTrue(any("Archived prior Daily Premarket Report HTML" in line for line in logs))
        self.assertTrue(any("Promoted new Daily Premarket Report HTML" in line for line in logs))
        self.assertTrue(any("Updated latest pointer for Daily Premarket Report HTML" in line for line in logs))

    def test_promote_report_artifact_preserves_live_on_missing_temp(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_path = root / "output" / "premarket.html"
            live_path.parent.mkdir(parents=True, exist_ok=True)
            live_path.write_text("old-live", encoding="utf-8")
            archive_dir = root / "archive" / "daily"

            with self.assertRaises(FileNotFoundError):
                report_lifecycle.promote_report_artifact(
                    report_label="Daily Premarket Report HTML",
                    live_path=live_path,
                    archive_dir=archive_dir,
                    archive_prefix="premarket",
                    temp_path=root / "tmp" / "missing.html",
                )
            live_text = live_path.read_text(encoding="utf-8")
            archive_exists = archive_dir.exists()

        self.assertEqual(live_text, "old-live")
        self.assertFalse(archive_exists)


if __name__ == "__main__":
    unittest.main()
