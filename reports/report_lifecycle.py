from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

REPORT_TIMEZONE = ZoneInfo("America/Vancouver")
Logger = Callable[[str], None]


def vancouver_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(REPORT_TIMEZONE)
    if now.tzinfo is None:
        return now.replace(tzinfo=REPORT_TIMEZONE)
    return now.astimezone(REPORT_TIMEZONE)


def vancouver_date_str(now: datetime | None = None) -> str:
    return vancouver_now(now).strftime("%Y-%m-%d")


def resolve_archive_path(
    archive_dir: Path,
    archive_prefix: str,
    extension: str,
    *,
    now: datetime | None = None,
) -> Path:
    local_now = vancouver_now(now)
    date_str = local_now.strftime("%Y-%m-%d")
    archive_dir.mkdir(parents=True, exist_ok=True)

    base_name = f"{archive_prefix}_{date_str}"
    candidate = archive_dir / f"{base_name}{extension}"
    if not candidate.exists():
        return candidate

    time_suffix = local_now.strftime("_%H%M")
    candidate = archive_dir / f"{base_name}{time_suffix}{extension}"
    if not candidate.exists():
        return candidate

    collision_index = 2
    while True:
        candidate = archive_dir / f"{base_name}{time_suffix}_{collision_index}{extension}"
        if not candidate.exists():
            return candidate
        collision_index += 1


def promote_report_artifact(
    *,
    report_label: str,
    live_path: Path,
    archive_dir: Path,
    archive_prefix: str,
    temp_path: Path,
    latest_pointer_path: Path | None = None,
    logger: Logger = print,
    now: datetime | None = None,
) -> tuple[Path, Path | None]:
    if not temp_path.exists():
        raise FileNotFoundError(f"temp artifact does not exist: {temp_path}")

    live_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path = None

    if live_path.exists():
        archive_path = resolve_archive_path(
            archive_dir,
            archive_prefix,
            live_path.suffix,
            now=now,
        )
        shutil.copy2(live_path, archive_path)
        logger(f"[OK] Archived prior {report_label} -> {archive_path}")

    os.replace(temp_path, live_path)
    logger(f"[OK] Promoted new {report_label} -> {live_path}")
    if latest_pointer_path is not None:
        latest_pointer_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(live_path, latest_pointer_path)
        logger(f"[OK] Updated latest pointer for {report_label} -> {latest_pointer_path}")
    return live_path, archive_path
