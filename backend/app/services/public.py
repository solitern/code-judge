"""Public API service: published weeks and judge run requests."""
from __future__ import annotations

import logging

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..models import Problem, Week
from ..schemas import PublicProblem, PublicSample, PublicWeek, PublicWeekSummary, RunResponse
from .rate_limit import client_ip, get_judge_limiter
from .runner_client import RunnerUnavailable, call_runner
from .scheduling import as_utc as _as_utc
from .scheduling import publish_due_weeks, utcnow

logger = logging.getLogger("app.public")


def _published_filter():
    now = utcnow()
    return (
        Week.status.in_(("PUBLISHED", "SCHEDULED")),
        Week.publish_at.is_not(None),
        Week.publish_at <= now,
    )


def _load_week(db: Session, week_id: int) -> Week | None:
    publish_due_weeks(db)
    return db.execute(
        select(Week)
        .options(
            selectinload(Week.problems).selectinload(Problem.testcases),
            selectinload(Week.notice),
        )
        .where(Week.id == week_id)
        .where(*_published_filter())
    ).scalar_one_or_none()


def _serialize_problem(p: Problem) -> PublicProblem:
    samples = [
        PublicSample(id=tc.id, input=tc.input_text, output=tc.expected_output)
        for tc in sorted(p.testcases, key=lambda t: (t.sort_order, t.id))
        if tc.enabled and tc.is_public
    ]
    return PublicProblem(
        id=p.stable_id,
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
        samples=samples,
    )


def serialize_public_week(week: Week) -> PublicWeek:
    problems = sorted(week.problems, key=lambda p: (p.sort_order, p.stable_id))
    return PublicWeek(
        id=week.id,
        week=week.week,
        title=week.title,
        notice=week.notice.content if week.notice else "",
        problems=[_serialize_problem(p) for p in problems],
    )


def list_published_weeks(db: Session) -> list[PublicWeekSummary]:
    publish_due_weeks(db)
    weeks = db.execute(
        select(Week)
        .options(selectinload(Week.problems))
        .where(*_published_filter())
        .order_by(Week.week.desc(), Week.id.desc())
    ).scalars().all()
    return [
        PublicWeekSummary(
            id=week.id,
            week=week.week,
            title=week.title,
            problem_count=len(week.problems),
            publish_at=_as_utc(week.publish_at),
        )
        for week in weeks
        if week.publish_at is not None
    ]


def get_current_week(db: Session) -> PublicWeek | None:
    publish_due_weeks(db)
    week = db.execute(
        select(Week)
        .options(
            selectinload(Week.problems).selectinload(Problem.testcases),
            selectinload(Week.notice),
        )
        .where(*_published_filter())
        .order_by(Week.week.desc())
        .limit(1)
    ).scalar_one_or_none()
    if week is None:
        return None
    return serialize_public_week(week)


def get_week_public(db: Session, week_id: int) -> PublicWeek:
    week = _load_week(db, week_id)
    if week is None:
        # Same response as nonexistent week; do not leak draft existence.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="周次不存在")
    return serialize_public_week(week)


def _get_problem_for_run(db: Session, week_id: int, problem_id: int) -> tuple[Week, Problem]:
    week = _load_week(db, week_id)
    if week is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="周次不存在")
    problem = next((p for p in week.problems if p.stable_id == problem_id), None)
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="题目不存在")
    return week, problem


def _validate_code(code: str) -> None:
    settings = get_settings()
    if not code or not code.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="代码不能为空")
    if len(code.encode("utf-8")) > settings.max_source_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="代码长度超出限制")


def _limits_for(p: Problem) -> dict:
    return {
        "time_limit_ms": p.time_limit_ms,
        "wall_time_ms": max(p.time_limit_ms * 3, 5000),
        "memory_limit_mb": p.memory_limit_mb,
        "output_limit_kb": p.output_limit_kb,
    }


async def run_sample(request: Request, db: Session, payload) -> RunResponse:
    _validate_code(payload.code)
    week, problem = _get_problem_for_run(db, payload.week_id, payload.problem_id)
    samples = [t for t in problem.testcases if t.enabled and t.is_public]
    samples.sort(key=lambda t: (t.sort_order, t.id))
    if payload.sample_index < 0 or payload.sample_index >= len(samples):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="样例序号无效")
    sample = samples[payload.sample_index]
    case = {
        "input": sample.input_text,
        "expected": sample.expected_output,
    }
    return await _dispatch_judge(request, payload.code, [case], problem, mode="sample", reveal=True)


async def run_custom(request: Request, db: Session, payload) -> RunResponse:
    _validate_code(payload.code)
    week, problem = _get_problem_for_run(db, payload.week_id, payload.problem_id)
    settings = get_settings()
    if len(payload.input.encode("utf-8")) > settings.max_custom_input_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="自定义输入长度超出限制")
    case = {"input": payload.input}
    return await _dispatch_judge(request, payload.code, [case], problem, mode="custom", reveal=True)


async def run_all(request: Request, db: Session, payload) -> RunResponse:
    _validate_code(payload.code)
    week, problem = _get_problem_for_run(db, payload.week_id, payload.problem_id)
    settings = get_settings()
    cases = sorted(
        [t for t in problem.testcases if t.enabled],
        key=lambda t: (t.sort_order, t.id),
    )
    if not cases:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该题目暂无测试案例")
    if len(cases) > settings.max_test_cases:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="该题测试案例数量超过判题服务配置，请联系管理员",
        )
    runner_cases = [{"input": t.input_text, "expected": t.expected_output} for t in cases]
    return await _dispatch_judge(request, payload.code, runner_cases, problem, mode="all", reveal=False)


async def _dispatch_judge(
    request: Request,
    code: str,
    cases: list[dict],
    problem: Problem,
    mode: str,
    reveal: bool,
) -> RunResponse:
    settings = get_settings()
    for c in cases:
        if len(c["input"].encode("utf-8")) > settings.max_case_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="测试案例输入长度超出限制")
        if c.get("expected") and len(c["expected"].encode("utf-8")) > settings.max_case_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="测试案例输出长度超出限制")

    payload = {
        "code": code,
        "cases": cases,
        "limits": {
            "compile_timeout_ms": 10000,
            "compile_memory_mb": 512,
            **_limits_for(problem),
        },
        "mode": mode,
    }

    async def task():
        return await call_runner(payload)

    limiter = get_judge_limiter()
    ip = client_ip(request)
    try:
        result = await limiter.run(request, ip, task)
    except RunnerUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    logger.info(
        "judge run mode=%s week_id=%s problem_id=%s ip=%s code_bytes=%d case_count=%d status=%s",
        mode, problem.week_id, problem.stable_id, ip, len(code.encode("utf-8")), len(cases), result.get("status"),
    )
    return RunResponse(**result) if isinstance(result, dict) else result
