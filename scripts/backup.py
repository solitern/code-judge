#!/usr/bin/env python3
"""Safely back up the SQLite database using the online backup API.

Usage:
  python scripts/backup.py [--output data/backup-YYYYMMDD-HHMMSS.db]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite 在线备份")
    parser.add_argument("--output", default=None, help="备份文件路径")
    args = parser.parse_args()

    settings = get_settings()
    db_path = settings.database_url.removeprefix("sqlite:///")
    if db_path == ":memory:":
        print("内存数据库无需备份")
        return 1
    if not Path(db_path).is_absolute():
        db_path = str(Path(db_path).resolve())
    source = Path(db_path)
    if not source.exists():
        print(f"数据库不存在: {source}")
        return 1

    output = Path(args.output) if args.output else Path("data") / f"backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.db"
    output.parent.mkdir(parents=True, exist_ok=True)

    dest = sqlite3.connect(str(output))
    src = sqlite3.connect(str(source))
    try:
        src.backup(dest)
    finally:
        dest.close()
        src.close()
    print(f"备份完成: {output} ({output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
