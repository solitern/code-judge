"""Admin service layer."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..auth.security import hash_password
from ..config import get_settings
from ..models import AdminUser, Problem, Solution, TestCase, Week, WeekNotice, WeekSnapshot
from ..schemas import (
    DashboardOut,
    ProblemOut,
    ProblemPreviewOut,
    SnapshotOut,
    SolutionOut,
    TestCaseImportItem,
    TestCaseOut,
    WeekJsonImport,
    WeekJsonImportResult,
    WeekOut,
    WeekPreviewOut,
)
from .public import _validate_code
from .runner_client import RunnerUnavailable, call_runner
from .scheduling import as_utc as _as_utc
from .scheduling import publish_due_weeks, utcnow

logger = logging.getLogger("app.admin")


# ---------------- bootstrap ----------------
def ensure_admin(db: Session) -> None:
    settings = get_settings()
    admin = db.execute(select(AdminUser).where(AdminUser.username == settings.admin_username)).scalar_one_or_none()
    if admin is None:
        admin = AdminUser(username=settings.admin_username, password_hash=hash_password(settings.admin_password))
        db.add(admin)
        db.commit()
        logger.info("created admin user '%s'", settings.admin_username)
    else:
        # Keep password in sync with env on first startup only?  For security,
        # we only create the admin once; change password via env + recreate
        # is documented.  If the env password changed, update it so container
        # restarts with a new ADMIN_PASSWORD are reflected.
        from ..auth.security import verify_password
        if not verify_password(settings.admin_password, admin.password_hash):
            admin.password_hash = hash_password(settings.admin_password)
            db.commit()
            logger.info("updated admin password for '%s' from ADMIN_PASSWORD", settings.admin_username)


# ---------------- dashboard ----------------
def _week_out(db: Session, week: Week) -> WeekOut:
    problem_count = len(week.problems) if week.problems else 0
    has_unverified = False
    for p in week.problems or []:
        if p.solution is not None and p.solution.code and not p.solution.verified:
            has_unverified = True
            break
    snapshot = db.execute(
        select(func.max(WeekSnapshot.version)).where(WeekSnapshot.week_id == week.id)
    ).scalar()
    return WeekOut(
        id=week.id,
        week=week.week,
        title=week.title,
        notice=week.notice.content if week.notice else "",
        status=week.status,
        publish_at=_as_utc(week.publish_at),
        published_at=_as_utc(week.published_at),
        archived_at=_as_utc(week.archived_at),
        created_at=_as_utc(week.created_at),
        updated_at=_as_utc(week.updated_at),
        problem_count=problem_count,
        version=snapshot or 0,
        has_unverified_solution=has_unverified,
    )


def dashboard(db: Session, runner_health: str = "unknown") -> DashboardOut:
    publish_due_weeks(db)
    weeks = db.execute(
        select(Week).options(selectinload(Week.problems).selectinload(Problem.solution)).order_by(Week.week.desc())
    ).scalars().all()

    now = utcnow()
    current = None
    next_scheduled = None
    draft_count = 0
    scheduled_count = 0
    published_count = 0
    archived_count = 0
    last_updated: datetime | None = None

    for w in weeks:
        if w.updated_at and (last_updated is None or _as_utc(w.updated_at) > _as_utc(last_updated)):
            last_updated = w.updated_at
        if w.status == "DRAFT":
            draft_count += 1
        elif w.status == "SCHEDULED":
            scheduled_count += 1
        elif w.status == "PUBLISHED":
            published_count += 1
        elif w.status == "ARCHIVED":
            archived_count += 1

        publish_at = _as_utc(w.publish_at)
        is_public_now = w.status in ("PUBLISHED", "SCHEDULED") and publish_at is not None and publish_at <= now
        if is_public_now and current is None:
            current = w
        if w.status == "SCHEDULED" and publish_at and publish_at > now:
            if next_scheduled is None or publish_at < _as_utc(next_scheduled.publish_at):
                next_scheduled = w

    settings = get_settings()
    return DashboardOut(
        current_public_week=_week_out(db, current) if current else None,
        next_scheduled_publish=_week_out(db, next_scheduled) if next_scheduled else None,
        draft_count=draft_count,
        scheduled_count=scheduled_count,
        published_count=published_count,
        archived_count=archived_count,
        last_updated_at=_as_utc(last_updated),
        runner_status=runner_health,
        runner_concurrency=0,
        judge_max_concurrency=settings.judge_max_concurrency,
        judge_queue_size=settings.judge_queue_size,
    )


# ---------------- weeks ----------------
def _load_week(db: Session, week_id: int, with_relations: bool = True) -> Week:
    stmt = select(Week).where(Week.id == week_id)
    if with_relations:
        stmt = stmt.options(
            selectinload(Week.problems)
            .selectinload(Problem.testcases),
            selectinload(Week.problems).selectinload(Problem.solution),
            selectinload(Week.notice),
        )
    week = db.execute(stmt).scalar_one_or_none()
    if week is None:
        raise HTTPException(status_code=404, detail="周次不存在")
    return week


def list_weeks(db: Session) -> list[WeekOut]:
    publish_due_weeks(db)
    weeks = db.execute(
        select(Week).options(
            selectinload(Week.problems).selectinload(Problem.solution),
            selectinload(Week.notice),
        ).order_by(Week.week.desc())
    ).scalars().all()
    return [_week_out(db, w) for w in weeks]


def create_week(db: Session, data) -> WeekOut:
    exists = db.execute(select(Week).where(Week.week == data.week)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="该周次已存在")
    week = Week(week=data.week, title=data.title, status="DRAFT")
    db.add(week)
    db.flush()
    _save_snapshot(db, week)
    db.commit()
    return _week_out(db, _load_week(db, week.id))


def update_week(db: Session, week_id: int, data) -> WeekOut:
    week = _load_week(db, week_id, with_relations=True)
    content_changed = data.title is not None or data.notice is not None
    if data.title is not None:
        week.title = data.title
    if data.notice is not None:
        if week.notice is None:
            week.notice = WeekNotice(content=data.notice)
        else:
            week.notice.content = data.notice
        week.updated_at = utcnow()
    if data.status is not None:
        _change_status(week, data.status, data.publish_at)
    elif data.publish_at is not None:
        _change_status(week, week.status, data.publish_at)
    db.flush()
    # A status-only transition does not change editable content. Avoid
    # serializing every testcase and solution when setting a schedule.
    if content_changed:
        _save_snapshot(db, week)
    db.commit()
    return _week_out(db, _load_week(db, week_id))


def import_week_json(db: Session, week_id: int, data: WeekJsonImport) -> WeekJsonImportResult:
    week = _load_week(db, week_id, with_relations=True)
    if data.week != week.week:
        raise HTTPException(
            status_code=400,
            detail=f"JSON 中的周次为 {data.week}，当前页面是周次 {week.week}",
        )

    settings = get_settings()
    for problem_data in data.problems:
        cases = [*problem_data.samples, *problem_data.test_cases]
        if len(cases) > settings.max_test_cases:
            raise HTTPException(
                status_code=400,
                detail=f"题目 {problem_data.id} 的测试案例超过 {settings.max_test_cases} 个",
            )
        for case in cases:
            _validate_case_size(case.input, case.output)

    existing = {problem.stable_id: problem for problem in week.problems}
    for problem_data in data.problems:
        problem = existing.get(problem_data.id)
        if problem is None:
            problem = Problem(week=week, stable_id=problem_data.id)
            db.add(problem)
            existing[problem_data.id] = problem

        problem.title = problem_data.title
        problem.description = problem_data.description
        problem.input_format = problem_data.input_format
        problem.output_format = problem_data.output_format
        problem.hint = problem_data.hint
        problem.template = problem_data.template
        problem.time_limit_ms = problem_data.time_limit_ms
        problem.memory_limit_mb = problem_data.memory_limit_mb
        problem.output_limit_kb = problem_data.output_limit_kb
        problem.sort_order = problem_data.sort_order if problem_data.sort_order is not None else problem_data.id
        problem.version = (problem.version or 0) + 1

        problem.testcases.clear()
        for index, case in enumerate(problem_data.samples):
            problem.testcases.append(TestCase(
                is_public=True,
                input_text=case.input,
                expected_output=case.output,
                sort_order=index,
                enabled=case.enabled,
            ))
        sample_count = len(problem_data.samples)
        for index, case in enumerate(problem_data.test_cases):
            problem.testcases.append(TestCase(
                is_public=False,
                input_text=case.input,
                expected_output=case.output,
                sort_order=sample_count + index,
                enabled=case.enabled,
            ))

        if problem.solution is not None:
            problem.solution.verified = False
            problem.solution.last_verified_at = None

    week.title = data.title
    week.updated_at = utcnow()
    db.flush()
    _save_snapshot(db, week)
    db.commit()

    return WeekJsonImportResult(
        title=week.title,
        problems_imported=len(data.problems),
        samples_imported=sum(len(problem.samples) for problem in data.problems),
        hidden_cases_imported=sum(len(problem.test_cases) for problem in data.problems),
    )


def _change_status(week: Week, new_status: str, publish_at: datetime | None = None) -> None:
    now = utcnow()
    if new_status == "DRAFT":
        week.status = "DRAFT"
        week.publish_at = None
        week.published_at = None
        week.archived_at = None
    elif new_status == "SCHEDULED":
        if publish_at is None:
            raise HTTPException(status_code=400, detail="设置定时发布必须提供 publish_at")
        publish_at = _as_utc(publish_at)
        if publish_at <= now:
            raise HTTPException(status_code=400, detail="定时发布时间必须晚于当前时间")
        week.status = "SCHEDULED"
        week.publish_at = publish_at
        week.published_at = None
        week.archived_at = None
    elif new_status == "PUBLISHED":
        week.status = "PUBLISHED"
        # This transition means "publish now".  In particular, do not keep a
        # future timestamp left over from a previous SCHEDULED state, because
        # the public query intentionally hides rows whose publish_at is future.
        week.publish_at = now
        week.published_at = now
        week.archived_at = None
    elif new_status == "ARCHIVED":
        week.status = "ARCHIVED"
        week.archived_at = now


def delete_week(db: Session, week_id: int) -> None:
    week = _load_week(db, week_id, with_relations=False)
    if week.status not in ("DRAFT", "SCHEDULED"):
        raise HTTPException(status_code=400, detail="只能删除草稿或待发布周次")
    db.delete(week)
    db.commit()


def duplicate_week(db: Session, week_id: int, new_week_number: int, new_title: str) -> WeekOut:
    src = _load_week(db, week_id, with_relations=True)
    exists = db.execute(select(Week).where(Week.week == new_week_number)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="目标周次编号已存在")
    new_week = Week(week=new_week_number, title=new_title, status="DRAFT")
    db.add(new_week)
    db.flush()
    if src.notice and src.notice.content:
        new_week.notice = WeekNotice(content=src.notice.content)
    for p in sorted(src.problems, key=lambda x: (x.sort_order, x.stable_id)):
        new_problem = Problem(
            week_id=new_week.id,
            stable_id=p.stable_id,
            title=p.title,
            description=p.description,
            input_format=p.input_format,
            output_format=p.output_format,
            hint=p.hint,
            template=p.template,
            time_limit_ms=p.time_limit_ms,
            memory_limit_mb=p.memory_limit_mb,
            output_limit_kb=p.output_limit_kb,
            sort_order=p.sort_order,
            version=1,
        )
        db.add(new_problem)
        db.flush()
        for tc in sorted(p.testcases, key=lambda x: (x.sort_order, x.id)):
            db.add(TestCase(
                problem_id=new_problem.id,
                is_public=tc.is_public,
                input_text=tc.input_text,
                expected_output=tc.expected_output,
                sort_order=tc.sort_order,
                enabled=tc.enabled,
            ))
        if p.solution and p.solution.code:
            db.add(Solution(problem_id=new_problem.id, code=p.solution.code, verified=False))
    db.flush()
    _save_snapshot(db, new_week)
    db.commit()
    return _week_out(db, _load_week(db, new_week.id))


# ---------------- preview ----------------
def preview_week(db: Session, week_id: int) -> WeekPreviewOut:
    week = _load_week(db, week_id, with_relations=True)
    problems = []
    for p in sorted(week.problems, key=lambda x: (x.sort_order, x.stable_id)):
        samples = [tc for tc in p.testcases if tc.enabled and tc.is_public]
        hidden = [tc for tc in p.testcases if tc.enabled and not tc.is_public]
        samples.sort(key=lambda t: (t.sort_order, t.id))
        hidden.sort(key=lambda t: (t.sort_order, t.id))
        problems.append(ProblemPreviewOut(
            id=p.stable_id,
            stable_id=p.stable_id,
            title=p.title,
            description=p.description,
            input_format=p.input_format,
            output_format=p.output_format,
            hint=p.hint,
            template=p.template,
            time_limit_ms=p.time_limit_ms,
            memory_limit_mb=p.memory_limit_mb,
            output_limit_kb=p.output_limit_kb,
            version=p.version,
            samples=[_tc_out(t) for t in samples],
            hidden_cases=[_tc_out(t) for t in hidden],
        ))
    return WeekPreviewOut(
        id=week.id,
        week=week.week,
        title=week.title,
        notice=week.notice.content if week.notice else "",
        status=week.status,
        is_preview=True,
        problems=problems,
    )


# ---------------- problems ----------------
def _tc_out(t: TestCase) -> TestCaseOut:
    return TestCaseOut(
        id=t.id,
        problem_id=t.problem_id,
        is_public=t.is_public,
        input=t.input_text,
        output=t.expected_output,
        sort_order=t.sort_order,
        enabled=t.enabled,
    )


def _problem_out(p: Problem) -> ProblemOut:
    return ProblemOut(
        id=p.id,
        week_id=p.week_id,
        stable_id=p.stable_id,
        title=p.title,
        description=p.description,
        input_format=p.input_format,
        output_format=p.output_format,
        hint=p.hint,
        template=p.template,
        time_limit_ms=p.time_limit_ms,
        memory_limit_mb=p.memory_limit_mb,
        output_limit_kb=p.output_limit_kb,
        sort_order=p.sort_order,
        version=p.version,
        has_solution=p.solution is not None and bool(p.solution.code),
        solution_verified=p.solution is not None and p.solution.verified,
    )


def get_problem(db: Session, week_id: int, problem_stable_id: int) -> ProblemOut:
    week = _load_week(db, week_id, with_relations=True)
    p = next((x for x in week.problems if x.stable_id == problem_stable_id), None)
    if p is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return _problem_out(p)


def upsert_problem(db: Session, week_id: int, problem_stable_id: int, data) -> ProblemOut:
    week = _load_week(db, week_id, with_relations=False)
    p = db.execute(
        select(Problem).where(Problem.week_id == week_id, Problem.stable_id == problem_stable_id)
    ).scalar_one_or_none()
    if p is None:
        p = Problem(week_id=week.id, stable_id=problem_stable_id)
        db.add(p)
    p.title = data.title
    p.description = data.description
    p.input_format = data.input_format
    p.output_format = data.output_format
    p.hint = data.hint
    p.template = data.template
    p.time_limit_ms = data.time_limit_ms
    p.memory_limit_mb = data.memory_limit_mb
    p.output_limit_kb = data.output_limit_kb
    p.sort_order = data.sort_order
    p.version = (p.version or 0) + 1
    db.flush()
    _save_snapshot(db, week)
    db.commit()
    db.expire_all()
    problem = db.execute(
        select(Problem).where(Problem.week_id == week_id, Problem.stable_id == problem_stable_id)
    ).scalar_one()
    return _problem_out(problem)


def delete_problem(db: Session, week_id: int, problem_stable_id: int) -> None:
    week = _load_week(db, week_id, with_relations=True)
    p = next((x for x in week.problems if x.stable_id == problem_stable_id), None)
    if p is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    db.delete(p)
    db.flush()
    _save_snapshot(db, week)
    db.commit()


# ---------------- test cases ----------------
def list_testcases(db: Session, week_id: int, problem_stable_id: int) -> list[TestCaseOut]:
    week = _load_week(db, week_id, with_relations=True)
    p = next((x for x in week.problems if x.stable_id == problem_stable_id), None)
    if p is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return [_tc_out(t) for t in sorted(p.testcases, key=lambda x: (x.sort_order, x.id))]


def upsert_testcase(db: Session, week_id: int, problem_stable_id: int, data) -> TestCaseOut:
    week = _load_week(db, week_id, with_relations=True)
    p = next((x for x in week.problems if x.stable_id == problem_stable_id), None)
    if p is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    _validate_case_size(data.input, data.output)
    settings = get_settings()
    if len(p.testcases) >= settings.max_test_cases:
        raise HTTPException(status_code=400, detail=f"每题最多允许 {settings.max_test_cases} 个测试案例")
    tc = TestCase(
        problem_id=p.id,
        is_public=data.is_public,
        input_text=data.input,
        expected_output=data.output,
        sort_order=data.sort_order,
        enabled=data.enabled,
    )
    db.add(tc)
    p.version = (p.version or 0) + 1
    db.flush()
    _save_snapshot(db, week)
    db.commit()
    return _tc_out(tc)


def update_testcase(db: Session, week_id: int, problem_stable_id: int, testcase_id: int, data) -> TestCaseOut:
    week = _load_week(db, week_id, with_relations=True)
    p = next((x for x in week.problems if x.stable_id == problem_stable_id), None)
    if p is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    tc = next((t for t in p.testcases if t.id == testcase_id), None)
    if tc is None:
        raise HTTPException(status_code=404, detail="测试案例不存在")
    _validate_case_size(data.input, data.output)
    tc.input_text = data.input
    tc.expected_output = data.output
    tc.is_public = data.is_public
    tc.sort_order = data.sort_order
    tc.enabled = data.enabled
    p.version = (p.version or 0) + 1
    db.flush()
    _save_snapshot(db, week)
    db.commit()
    return _tc_out(tc)


def delete_testcase(db: Session, week_id: int, problem_stable_id: int, testcase_id: int) -> None:
    week = _load_week(db, week_id, with_relations=True)
    p = next((x for x in week.problems if x.stable_id == problem_stable_id), None)
    if p is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    tc = next((t for t in p.testcases if t.id == testcase_id), None)
    if tc is None:
        raise HTTPException(status_code=404, detail="测试案例不存在")
    db.delete(tc)
    p.version = (p.version or 0) + 1
    db.flush()
    _save_snapshot(db, week)
    db.commit()


def _validate_case_size(input_text: str, output_text: str) -> None:
    settings = get_settings()
    if len(input_text.encode("utf-8")) > settings.max_case_bytes:
        raise HTTPException(status_code=400, detail="测试案例输入超出大小限制")
    if len(output_text.encode("utf-8")) > settings.max_case_bytes:
        raise HTTPException(status_code=400, detail="测试案例输出超出大小限制")


def import_cases_json(
    db: Session,
    week_id: int,
    problem_stable_id: int,
    cases: list[TestCaseImportItem],
    public_default: bool = False,
) -> int:
    week = _load_week(db, week_id, with_relations=True)
    p = next((x for x in week.problems if x.stable_id == problem_stable_id), None)
    if p is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    settings = get_settings()
    if len(p.testcases) + len(cases) > settings.max_test_cases:
        raise HTTPException(status_code=400, detail=f"导入后测试案例不能超过 {settings.max_test_cases} 个")
    max_sort = max([t.sort_order for t in p.testcases], default=0)
    for i, c in enumerate(cases):
        _validate_case_size(c.input, c.output)
        db.add(TestCase(
            problem_id=p.id,
            is_public=public_default if c.is_public is None else c.is_public,
            input_text=c.input,
            expected_output=c.output,
            sort_order=max_sort + i + 1,
            enabled=c.enabled,
        ))
    p.version = (p.version or 0) + 1
    db.flush()
    _save_snapshot(db, week)
    db.commit()
    return len(cases)


# ---------------- solution ----------------
def get_solution(db: Session, week_id: int, problem_stable_id: int) -> SolutionOut:
    week = _load_week(db, week_id, with_relations=True)
    p = next((x for x in week.problems if x.stable_id == problem_stable_id), None)
    if p is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    if p.solution is None:
        return SolutionOut(problem_id=p.id, code="", verified=False, last_verified_at=None)
    return SolutionOut(problem_id=p.id, code=p.solution.code, verified=p.solution.verified, last_verified_at=p.solution.last_verified_at)


def upsert_solution(db: Session, week_id: int, problem_stable_id: int, code: str) -> SolutionOut:
    settings = get_settings()
    if len(code.encode("utf-8")) > settings.max_source_bytes:
        raise HTTPException(status_code=400, detail="标准答案代码超出大小限制")
    week = _load_week(db, week_id, with_relations=True)
    p = next((x for x in week.problems if x.stable_id == problem_stable_id), None)
    if p is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    sol = p.solution
    if sol is None:
        sol = Solution(problem_id=p.id, code=code)
        db.add(sol)
    else:
        sol.code = code
        sol.verified = False
        sol.last_verified_at = None
    p.version = (p.version or 0) + 1
    db.flush()
    _save_snapshot(db, week)
    db.commit()
    return SolutionOut(problem_id=p.id, code=sol.code, verified=sol.verified, last_verified_at=sol.last_verified_at)


async def verify_solution(db: Session, week_id: int, problem_stable_id: int) -> dict:
    week = _load_week(db, week_id, with_relations=True)
    p = next((x for x in week.problems if x.stable_id == problem_stable_id), None)
    if p is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    if p.solution is None or not p.solution.code.strip():
        raise HTTPException(status_code=400, detail="尚未上传标准答案")
    cases = sorted([t for t in p.testcases if t.enabled], key=lambda t: (t.sort_order, t.id))
    if not cases:
        raise HTTPException(status_code=400, detail="该题目暂无测试案例")
    settings = get_settings()
    if len(cases) > settings.max_test_cases:
        raise HTTPException(status_code=400, detail=f"测试案例不能超过 {settings.max_test_cases} 个")
    payload = {
        "code": p.solution.code,
        "cases": [{"input": t.input_text, "expected": t.expected_output} for t in cases],
        "limits": {
            "compile_timeout_ms": 10000,
            "compile_memory_mb": 512,
            "time_limit_ms": p.time_limit_ms,
            "wall_time_ms": max(p.time_limit_ms * 3, 5000),
            "memory_limit_mb": p.memory_limit_mb,
            "output_limit_kb": p.output_limit_kb,
        },
        "mode": "verify",
    }
    try:
        result = await call_runner(payload)
    except RunnerUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    passed = result.get("status") == "ACCEPTED"
    if p.solution:
        p.solution.verified = passed
        p.solution.last_verified_at = utcnow() if passed else p.solution.last_verified_at
        db.commit()
    result["reveal"] = True
    return result


# ---------------- preview runs ----------------
def _get_problem_for_preview(db: Session, week_id: int, problem_stable_id: int) -> Problem:
    week = _load_week(db, week_id, with_relations=True)
    p = next((x for x in week.problems if x.stable_id == problem_stable_id), None)
    if p is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return p


async def _dispatch_preview_judge(db: Session, week_id: int, problem_stable_id: int, code: str, cases: list[dict], mode: str) -> dict:
    _validate_code(code)
    p = _get_problem_for_preview(db, week_id, problem_stable_id)
    settings = get_settings()
    if len(cases) > settings.max_test_cases:
        raise HTTPException(status_code=400, detail=f"测试案例不能超过 {settings.max_test_cases} 个")
    for case in cases:
        if len(case.get("input", "").encode("utf-8")) > settings.max_case_bytes:
            raise HTTPException(status_code=400, detail="测试案例输入长度超出限制")
        expected = case.get("expected")
        if expected is not None and len(expected.encode("utf-8")) > settings.max_case_bytes:
            raise HTTPException(status_code=400, detail="测试案例输出长度超出限制")
    payload = {
        "code": code,
        "cases": cases,
        "limits": {
            "compile_timeout_ms": 10000,
            "compile_memory_mb": 512,
            "time_limit_ms": p.time_limit_ms,
            "wall_time_ms": max(p.time_limit_ms * 3, 5000),
            "memory_limit_mb": p.memory_limit_mb,
            "output_limit_kb": p.output_limit_kb,
        },
        "mode": mode,
    }
    try:
        result = await call_runner(payload)
    except RunnerUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    result["reveal"] = True
    return result


async def run_preview_sample(db: Session, week_id: int, problem_stable_id: int, code: str, sample_index: int) -> dict:
    p = _get_problem_for_preview(db, week_id, problem_stable_id)
    samples = sorted([t for t in p.testcases if t.enabled and t.is_public], key=lambda t: (t.sort_order, t.id))
    if sample_index < 0 or sample_index >= len(samples):
        raise HTTPException(status_code=400, detail="样例序号无效")
    s = samples[sample_index]
    return await _dispatch_preview_judge(db, week_id, problem_stable_id, code, [{"input": s.input_text, "expected": s.expected_output}], "sample")


async def run_preview_custom(db: Session, week_id: int, problem_stable_id: int, code: str, input_text: str) -> dict:
    settings = get_settings()
    if len(input_text.encode("utf-8")) > settings.max_custom_input_bytes:
        raise HTTPException(status_code=400, detail="自定义输入长度超出限制")
    return await _dispatch_preview_judge(db, week_id, problem_stable_id, code, [{"input": input_text}], "custom")


async def run_preview_all(db: Session, week_id: int, problem_stable_id: int, code: str) -> dict:
    p = _get_problem_for_preview(db, week_id, problem_stable_id)
    cases = sorted([t for t in p.testcases if t.enabled], key=lambda t: (t.sort_order, t.id))
    if not cases:
        raise HTTPException(status_code=400, detail="该题目暂无测试案例")
    return await _dispatch_preview_judge(
        db, week_id, problem_stable_id, code,
        [{"input": t.input_text, "expected": t.expected_output} for t in cases],
        "all",
    )


# ---------------- snapshots ----------------
def _week_snapshot_data(week: Week) -> dict[str, Any]:
    problems = []
    for p in sorted(week.problems or [], key=lambda x: (x.sort_order, x.stable_id)):
        problems.append({
            "stable_id": p.stable_id,
            "title": p.title,
            "description": p.description,
            "input_format": p.input_format,
            "output_format": p.output_format,
            "hint": p.hint,
            "template": p.template,
            "time_limit_ms": p.time_limit_ms,
            "memory_limit_mb": p.memory_limit_mb,
            "output_limit_kb": p.output_limit_kb,
            "sort_order": p.sort_order,
            "version": p.version,
            "testcases": [
                {
                    "is_public": t.is_public,
                    "input": t.input_text,
                    "output": t.expected_output,
                    "sort_order": t.sort_order,
                    "enabled": t.enabled,
                }
                for t in sorted(p.testcases or [], key=lambda x: (x.sort_order, x.id))
            ],
            "solution": {"code": p.solution.code, "verified": p.solution.verified} if p.solution else None,
        })
    return {
        "week": week.week,
        "title": week.title,
        "notice": week.notice.content if week.notice else "",
        "status": week.status,
        "publish_at": week.publish_at.isoformat() if week.publish_at else None,
        "published_at": week.published_at.isoformat() if week.published_at else None,
        "archived_at": week.archived_at.isoformat() if week.archived_at else None,
        "problems": problems,
    }


def _save_snapshot(db: Session, week: Week) -> WeekSnapshot:
    db.flush()
    week_id = week.id
    latest = db.execute(
        select(func.max(WeekSnapshot.version)).where(WeekSnapshot.week_id == week_id)
    ).scalar() or 0
    # Relationship collections may already have been loaded before rows were
    # inserted/deleted through their foreign keys. Reload the complete graph
    # from the flushed transaction so snapshots never serialize stale cases.
    db.expire_all()
    fresh_week = db.execute(
        select(Week)
        .options(
            selectinload(Week.problems).selectinload(Problem.testcases),
            selectinload(Week.problems).selectinload(Problem.solution),
            selectinload(Week.notice),
        )
        .where(Week.id == week_id)
        .execution_options(populate_existing=True)
    ).scalar_one()
    snap = WeekSnapshot(
        week_id=fresh_week.id,
        version=latest + 1,
        data_json=json.dumps(_week_snapshot_data(fresh_week), ensure_ascii=False),
    )
    db.add(snap)
    db.flush()
    # Keep at most 10 snapshots per week.
    old = db.execute(
        select(WeekSnapshot)
        .where(WeekSnapshot.week_id == week.id)
        .order_by(WeekSnapshot.version.desc())
        .offset(10)
    ).scalars().all()
    for s in old:
        db.delete(s)
    return snap


def list_snapshots(db: Session, week_id: int) -> list[SnapshotOut]:
    week = _load_week(db, week_id, with_relations=False)
    snaps = db.execute(
        select(WeekSnapshot).where(WeekSnapshot.week_id == week.id).order_by(WeekSnapshot.version.desc()).limit(20)
    ).scalars().all()
    return [SnapshotOut(id=s.id, week_id=s.week_id, version=s.version, created_at=_as_utc(s.created_at)) for s in snaps]


def rollback_snapshot(db: Session, week_id: int, snapshot_id: int) -> WeekOut:
    week = _load_week(db, week_id, with_relations=True)
    snap = db.execute(
        select(WeekSnapshot).where(WeekSnapshot.id == snapshot_id, WeekSnapshot.week_id == week.id)
    ).scalar_one_or_none()
    if snap is None:
        raise HTTPException(status_code=404, detail="版本快照不存在")
    data = json.loads(snap.data_json)
    week.title = data.get("title", week.title)
    notice_content = data.get("notice", "")
    if week.notice is None:
        week.notice = WeekNotice(content=notice_content)
    else:
        week.notice.content = notice_content
    week.status = data.get("status", "DRAFT")
    for field in ("publish_at", "published_at", "archived_at"):
        val = data.get(field)
        setattr(week, field, datetime.fromisoformat(val) if val else None)
    # Remove problems not in snapshot.
    snapshot_stable_ids = {p["stable_id"] for p in data["problems"]}
    for p in list(week.problems):
        if p.stable_id not in snapshot_stable_ids:
            db.delete(p)
    db.flush()
    for pdata in data["problems"]:
        p = next((x for x in week.problems if x.stable_id == pdata["stable_id"]), None)
        if p is None:
            p = Problem(week_id=week.id, stable_id=pdata["stable_id"])
            db.add(p)
            db.flush()
        p.title = pdata.get("title", "")
        p.description = pdata.get("description", "")
        p.input_format = pdata.get("input_format", "")
        p.output_format = pdata.get("output_format", "")
        p.hint = pdata.get("hint", "")
        p.template = pdata.get("template", "")
        p.time_limit_ms = pdata.get("time_limit_ms", 2000)
        p.memory_limit_mb = pdata.get("memory_limit_mb", 256)
        p.output_limit_kb = pdata.get("output_limit_kb", 1024)
        p.sort_order = pdata.get("sort_order", 0)
        p.version = pdata.get("version", 1)
        # Replace test cases.
        for t in list(p.testcases):
            db.delete(t)
        db.flush()
        for i, tdata in enumerate(pdata.get("testcases", [])):
            db.add(TestCase(
                problem_id=p.id,
                is_public=tdata.get("is_public", False),
                input_text=tdata.get("input", ""),
                expected_output=tdata.get("output", ""),
                sort_order=tdata.get("sort_order", i),
                enabled=tdata.get("enabled", True),
            ))
        sol_data = pdata.get("solution")
        if sol_data and sol_data.get("code"):
            if p.solution is None:
                p.solution = Solution(problem_id=p.id, code=sol_data["code"])
            else:
                p.solution.code = sol_data["code"]
            p.solution.verified = bool(sol_data.get("verified", False))
        elif p.solution is not None:
            p.solution.code = ""
            p.solution.verified = False
    db.flush()
    _save_snapshot(db, week)
    db.commit()
    return _week_out(db, _load_week(db, week_id))
