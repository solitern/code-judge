"""Import week*.json files into the database (idempotent)."""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Problem, Solution, TestCase, Week
from ..schemas import ImportReport


def _legacy_solution_code(pdata: dict) -> str | None:
    for key in ("solution", "standard_answer", "answer"):
        value = pdata.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def import_legacy_json(db: Session, path: str = "example", dry_run: bool = False) -> ImportReport:
    base = Path(path)
    report = ImportReport(dry_run=dry_run)
    if not base.exists():
        report.errors.append(f"路径不存在: {path}")
        return report

    files = sorted(base.glob("week*.json"))
    if not files:
        report.errors.append(f"未在 {path} 找到 week*.json 文件")
        return report

    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:
            report.errors.append(f"{f.name}: JSON 解析失败: {exc}")
            continue

        week_no = int(data.get("week", 0))
        title = data.get("title", "")
        problems_data = data.get("problems", [])
        if not week_no or not problems_data:
            report.errors.append(f"{f.name}: 缺少 week 或 problems 字段")
            continue

        week = db.execute(select(Week).where(Week.week == week_no)).scalar_one_or_none()
        if week is None:
            report.weeks_imported += 1
            report.details.append(f"将创建周次 week={week_no} ({title})")
            if not dry_run:
                week = Week(week=week_no, title=title, status="DRAFT")
                db.add(week)
                db.flush()
        else:
            report.weeks_updated += 1
            report.details.append(f"周次 week={week_no} 已存在，将更新其题目")
            if not dry_run:
                week.title = title

        if week is None:
            if dry_run:
                for pdata in problems_data:
                    report.problems_imported += 1
                    report.samples_imported += len(pdata.get("samples", []))
                    report.hidden_cases_imported += len(pdata.get("testCases", pdata.get("test_cases", [])))
                    if _legacy_solution_code(pdata):
                        report.solutions_imported += 1
                    report.details.append(f"  将导入题目 week={week_no} problem={pdata.get('id')}")
            continue

        for pdata in problems_data:
            stable_id = int(pdata.get("id", 0))
            if not stable_id:
                report.errors.append(f"{f.name}: 题目缺少 id")
                continue
            problem = next(
                (p for p in week.problems if p.stable_id == stable_id) if week.problems is not None else None,
                None,
            )
            if problem is None and week.id:
                problem = db.execute(
                    select(Problem).where(Problem.week_id == week.id, Problem.stable_id == stable_id)
                ).scalar_one_or_none()
            if problem is None:
                if not dry_run:
                    problem = Problem(week_id=week.id, stable_id=stable_id)
                    db.add(problem)
                    db.flush()
                report.problems_imported += 1
                report.details.append(f"  将导入题目 week={week_no} problem={stable_id}")
            else:
                report.details.append(f"  题目 week={week_no} problem={stable_id} 已存在，将更新内容")

            if not dry_run and problem is not None:
                problem.title = pdata.get("title", "")
                problem.description = pdata.get("description", "")
                problem.input_format = pdata.get("inputFormat", pdata.get("input_format", ""))
                problem.output_format = pdata.get("outputFormat", pdata.get("output_format", ""))
                problem.hint = pdata.get("hint", "")
                problem.template = pdata.get("template", "")
                problem.sort_order = stable_id
                problem.version = (problem.version or 0) + 1
                # Idempotent re-import: the JSON file is the source of truth for
                # test cases, so replace existing test cases when re-importing.
                problem.testcases.clear()

            solution_code = _legacy_solution_code(pdata)
            if solution_code:
                report.solutions_imported += 1
                if not dry_run and problem is not None:
                    if problem.solution is None:
                        problem.solution = Solution(code=solution_code, verified=False)
                    else:
                        problem.solution.code = solution_code
                        problem.solution.verified = False
                        problem.solution.last_verified_at = None

            # Samples -> public test cases
            samples = pdata.get("samples", [])
            for i, s in enumerate(samples):
                if not isinstance(s, dict):
                    continue
                report.samples_imported += 1
                if not dry_run and problem is not None:
                    problem.testcases.append(TestCase(
                        is_public=True,
                        input_text=s.get("input", ""),
                        expected_output=s.get("output", ""),
                        sort_order=i,
                        enabled=True,
                    ))
            # testCases -> hidden test cases
            cases = pdata.get("testCases", pdata.get("test_cases", []))
            for i, c in enumerate(cases):
                if not isinstance(c, dict):
                    continue
                report.hidden_cases_imported += 1
                if not dry_run and problem is not None:
                    problem.testcases.append(TestCase(
                        is_public=False,
                        input_text=c.get("input", ""),
                        expected_output=c.get("output", ""),
                        sort_order=len(samples) + i,
                        enabled=True,
                    ))

    if not dry_run:
        db.commit()
    else:
        db.rollback()
    return report
