"""Utility to archive old SIEMerl log data to CSV files."""
from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Tuple

from db import LogEntry, SessionLocal


ARCHIVE_ROOT = Path("Archiv")


def _group_logs_by_year_month(logs: Iterable[LogEntry]) -> dict[Tuple[int, int], list[LogEntry]]:
    grouped: dict[Tuple[int, int], list[LogEntry]] = {}
    for log in logs:
        timestamp = log.timestamp or datetime.utcnow()
        grouped.setdefault((timestamp.year, timestamp.month), []).append(log)
    return grouped


def archive_old_logs(retention_days: int = 30) -> int:
    """Archive logs older than ``retention_days`` to monthly CSV files.

    Logs are written to ``Archiv/<year>/<year>-<month>.csv`` and removed
    from the database after successful export.
    """
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    session = SessionLocal()

    try:
        old_logs = session.query(LogEntry).filter(LogEntry.timestamp < cutoff).all()
        if not old_logs:
            return 0

        grouped_logs = _group_logs_by_year_month(old_logs)

        for (year, month), logs in grouped_logs.items():
            year_dir = ARCHIVE_ROOT / str(year)
            year_dir.mkdir(parents=True, exist_ok=True)
            file_path = year_dir / f"{year}-{month:02d}.csv"

            is_new_file = not file_path.exists()
            with file_path.open("a", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                if is_new_file:
                    writer.writerow(["id", "source", "level", "message", "timestamp", "client_ip"])
                for log in logs:
                    writer.writerow(
                        [
                            log.id,
                            log.source,
                            log.level,
                            log.message,
                            log.timestamp.isoformat() if log.timestamp else None,
                            log.client_ip,
                        ]
                    )

        session.query(LogEntry).filter(LogEntry.id.in_([log.id for log in old_logs])).delete(
            synchronize_session=False
        )
        session.commit()
        return len(old_logs)
    finally:
        session.close()


if __name__ == "__main__":
    archived_count = archive_old_logs()
    print(f"Archived {archived_count} log entries older than 30 days.")
