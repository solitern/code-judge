from __future__ import annotations

import json
from pathlib import Path

from app.db import SessionLocal
from app.services.import_legacy import import_legacy_json


def _write_legacy(tmp_path):
    problems_dir = tmp_path / "problems"
    problems_dir.mkdir()
    data = {
        "week": 30,
        "title": "第三十周",
        "problems": [
            {
                "id": 1,
                "title": "测试题",
                "description": "描述",
                "inputFormat": "输入",
                "outputFormat": "输出",
                "hint": "提示",
                "samples": [{"input": "1", "output": "2", "explanation": "说明"}],
                "testCases": [{"input": "3", "output": "4"}, {"input": "5", "output": "6"}],
                "template": "#include <stdio.h>\nint main(){return 0;}",
                "solution": "#include <stdio.h>\nint main(){return 0;}\n",
            }
        ],
    }
    (problems_dir / "week30.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return problems_dir


def test_import_legacy_idempotent(tmp_path):
    from app.db import SessionLocal
    problems_dir = _write_legacy(tmp_path)
    db = SessionLocal()
    report = import_legacy_json(db, str(problems_dir), dry_run=False)
    assert report.problems_imported == 1
    assert report.samples_imported == 1
    assert report.hidden_cases_imported == 2
    assert report.solutions_imported == 1
    # Second import should not duplicate problems.
    report2 = import_legacy_json(db, str(problems_dir), dry_run=False)
    assert report2.problems_imported == 0
    assert report2.weeks_updated == 1
    from sqlalchemy import func, select
    from app.models import Problem, Solution, TestCase, Week
    week = db.execute(select(Week).where(Week.week == 30)).scalar_one()
    problems = db.execute(select(Problem).where(Problem.week_id == week.id)).scalars().all()
    assert len(problems) == 1
    cases = db.execute(select(TestCase).where(TestCase.problem_id == problems[0].id)).scalars().all()
    # Re-import replaces source-controlled cases instead of duplicating them.
    assert len(cases) == 3
    solution = db.execute(select(Solution).where(Solution.problem_id == problems[0].id)).scalar_one()
    assert "stdio.h" in solution.code
    assert solution.verified is False


def test_import_dry_run_makes_no_changes(tmp_path):
    from app.db import SessionLocal
    problems_dir = _write_legacy(tmp_path)
    db = SessionLocal()
    report = import_legacy_json(db, str(problems_dir), dry_run=True)
    assert report.dry_run is True
    from sqlalchemy import select
    from app.models import Week
    assert db.execute(select(Week).where(Week.week == 30)).scalar_one_or_none() is None
