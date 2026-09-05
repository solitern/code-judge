#!/usr/bin/env python3
"""Import week*.json files into SQLite.

Usage:
  python scripts/import_legacy_json.py --path example
  python scripts/import_legacy_json.py --path example --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import ensure_data_dir, get_settings  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.services.import_legacy import import_legacy_json  # noqa: E402
from app.services.admin import ensure_admin  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="导入 week*.json 题目")
    parser.add_argument("--path", default="example")
    parser.add_argument("--dry-run", action="store_true", help="仅报告将要导入的内容")
    args = parser.parse_args()

    settings = get_settings()
    ensure_data_dir(settings)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        ensure_admin(db)
        report = import_legacy_json(db, args.path, dry_run=args.dry_run)
        print(f"dry_run: {report.dry_run}")
        print(f"weeks_imported: {report.weeks_imported}")
        print(f"weeks_updated: {report.weeks_updated}")
        print(f"problems_imported: {report.problems_imported}")
        print(f"samples_imported: {report.samples_imported}")
        print(f"hidden_cases_imported: {report.hidden_cases_imported}")
        print("details:")
        for d in report.details:
            print("  " + d)
        if report.errors:
            print("errors:")
            for e in report.errors:
                print("  " + e)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
