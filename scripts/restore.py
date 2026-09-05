#!/usr/bin/env python3
"""Restore a SQLite backup created by scripts/backup.py.

Usage:
  python scripts/restore.py --input data/backup-YYYYMMDD-HHMMSS.db [--force]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="恢复 SQLite 备份")
    parser.add_argument("--input", required=True, help="备份文件路径")
    parser.add_argument("--force", action="store_true", help="覆盖现有数据库")
    args = parser.parse_args()

    settings = get_settings()
    db_path = settings.database_url.removeprefix("sqlite:///")
    if db_path == ":memory:":
        print("无法恢复到内存数据库")
        return 1
    if not Path(db_path).is_absolute():
        db_path = str(Path(db_path).resolve())
    target = Path(db_path)
    backup_file = Path(args.input)
    if not backup_file.exists():
        print(f"备份文件不存在: {backup_file}")
        return 1
    if target.exists() and not args.force:
        print(f"目标数据库已存在: {target}，如需覆盖请加 --force")
        return 1

    target.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(backup_file))
    dest = sqlite3.connect(str(target))
    try:
        src.backup(dest)
    finally:
        dest.close()
        src.close()
    print(f"恢复完成: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
