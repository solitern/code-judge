"""Admin API routes."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..auth.deps import get_current_admin
from ..auth.security import create_session_token, new_csrf_token, verify_password
from ..config import get_settings
from ..db import get_db
from ..models import AdminUser, Problem, TestCase
from ..schemas import (
    DashboardOut,
    ImportLegacyRequest,
    ImportReport,
    LoginRequest,
    PreviewRunAllRequest,
    PreviewRunCustomRequest,
    PreviewRunSampleRequest,
    ProblemOut,
    ProblemUpsert,
    SnapshotOut,
    SolutionOut,
    SolutionUpsert,
    TestCaseImportRequest,
    TestCaseImportResult,
    TestCaseOut,
    TestCaseUpsert,
    WeekCreate,
    WeekDuplicate,
    WeekJsonImport,
    WeekJsonImportResult,
    WeekOut,
    WeekPreviewOut,
    WeekUpdate,
)
from ..services import admin as service
from ..services.import_legacy import import_legacy_json

router = APIRouter(prefix="/admin", tags=["admin"])

MAX_WEEK_JSON_BYTES = 5 * 1024 * 1024


@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    settings = get_settings()
    service.ensure_admin(db)
    admin = db.query(AdminUser).filter(AdminUser.username == payload.username).one_or_none()
    if admin is None or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    session_token = create_session_token(admin.username, settings.secret_key, settings.cookie_max_age_seconds)
    csrf = new_csrf_token()
    secure = settings.cookie_secure
    response.set_cookie(
        "admin_session",
        session_token,
        max_age=settings.cookie_max_age_seconds,
        httponly=True,
        secure=secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    response.set_cookie(
        "csrf_token",
        csrf,
        max_age=settings.cookie_max_age_seconds,
        httponly=False,
        secure=secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    return {"username": admin.username, "csrf_token": csrf}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("admin_session", path="/")
    response.delete_cookie("csrf_token", path="/")
    return {"ok": True}


@router.get("/me")
def me(username: str = Depends(get_current_admin)):
    return {"username": username}


# ---------------- dashboard ----------------
@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(
    db: Session = Depends(get_db),
    username: str = Depends(get_current_admin),
):
    from ..services.runner_client import runner_health

    return service.dashboard(db, runner_health=await runner_health())


# ---------------- weeks ----------------
@router.get("/weeks", response_model=list[WeekOut])
def list_weeks(db: Session = Depends(get_db), username: str = Depends(get_current_admin)):
    return service.list_weeks(db)


@router.post("/weeks", response_model=WeekOut, status_code=201)
def create_week(payload: WeekCreate, db: Session = Depends(get_db), username: str = Depends(get_current_admin)):
    return service.create_week(db, payload)


@router.get("/weeks/{week_id}", response_model=WeekOut)
def get_week(week_id: int, db: Session = Depends(get_db), username: str = Depends(get_current_admin)):
    return service._week_out(db, service._load_week(db, week_id))


@router.patch("/weeks/{week_id}", response_model=WeekOut)
def update_week(week_id: int, payload: WeekUpdate, db: Session = Depends(get_db), username: str = Depends(get_current_admin)):
    return service.update_week(db, week_id, payload)


@router.post("/weeks/{week_id}/import-json", response_model=WeekJsonImportResult)
async def import_week_json(
    week_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    username: str = Depends(get_current_admin),
):
    content = await file.read(MAX_WEEK_JSON_BYTES + 1)
    if len(content) > MAX_WEEK_JSON_BYTES:
        raise HTTPException(status_code=400, detail="JSON 文件过大（最大 5 MB）")
    try:
        raw = json.loads(content.decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="JSON 文件必须使用 UTF-8 编码") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"JSON 格式错误：第 {exc.lineno} 行第 {exc.colno} 列",
        ) from exc

    try:
        payload = WeekJsonImport.model_validate(raw)
    except ValidationError as exc:
        error = exc.errors(include_url=False)[0]
        field = ".".join(str(part) for part in error["loc"]) or "根对象"
        raise HTTPException(
            status_code=422,
            detail=f"JSON 字段 {field} 校验失败：{error['msg']}",
        ) from exc
    return service.import_week_json(db, week_id, payload)


@router.delete("/weeks/{week_id}", status_code=204)
def delete_week(week_id: int, db: Session = Depends(get_db), username: str = Depends(get_current_admin)):
    service.delete_week(db, week_id)


@router.post("/weeks/{week_id}/duplicate", response_model=WeekOut)
def duplicate_week(
    week_id: int,
    payload: WeekDuplicate,
    db: Session = Depends(get_db),
    username: str = Depends(get_current_admin),
):
    return service.duplicate_week(db, week_id, payload.week, payload.title)


@router.get("/weeks/{week_id}/preview", response_model=WeekPreviewOut)
def preview_week(
    week_id: int,
    response: Response,
    db: Session = Depends(get_db),
    username: str = Depends(get_current_admin),
):
    response.headers["Cache-Control"] = "no-store"
    return service.preview_week(db, week_id)


# ---------------- problems ----------------
@router.get("/weeks/{week_id}/problems", response_model=list[ProblemOut])
def list_problems(week_id: int, db: Session = Depends(get_db), username: str = Depends(get_current_admin)):
    week = service._load_week(db, week_id)
    return [service._problem_out(p) for p in sorted(week.problems, key=lambda x: (x.sort_order, x.stable_id))]


@router.get("/weeks/{week_id}/problems/{problem_stable_id}", response_model=ProblemOut)
def get_problem(week_id: int, problem_stable_id: int, db: Session = Depends(get_db), username: str = Depends(get_current_admin)):
    return service.get_problem(db, week_id, problem_stable_id)


@router.put("/weeks/{week_id}/problems/{problem_stable_id}", response_model=ProblemOut)
def upsert_problem(
    week_id: int,
    problem_stable_id: int,
    payload: ProblemUpsert,
    db: Session = Depends(get_db),
    username: str = Depends(get_current_admin),
):
    return service.upsert_problem(db, week_id, problem_stable_id, payload)


@router.delete("/weeks/{week_id}/problems/{problem_stable_id}", status_code=204)
def delete_problem(week_id: int, problem_stable_id: int, db: Session = Depends(get_db), username: str = Depends(get_current_admin)):
    service.delete_problem(db, week_id, problem_stable_id)


# ---------------- test cases ----------------
@router.get("/weeks/{week_id}/problems/{problem_stable_id}/testcases", response_model=list[TestCaseOut])
def list_testcases(week_id: int, problem_stable_id: int, db: Session = Depends(get_db), username: str = Depends(get_current_admin)):
    return service.list_testcases(db, week_id, problem_stable_id)


@router.post("/weeks/{week_id}/problems/{problem_stable_id}/testcases", response_model=TestCaseOut, status_code=201)
def add_testcase(
    week_id: int,
    problem_stable_id: int,
    payload: TestCaseUpsert,
    db: Session = Depends(get_db),
    username: str = Depends(get_current_admin),
):
    return service.upsert_testcase(db, week_id, problem_stable_id, payload)


@router.patch("/testcases/{testcase_id}", response_model=TestCaseOut)
def update_testcase(
    testcase_id: int,
    payload: TestCaseUpsert,
    db: Session = Depends(get_db),
    username: str = Depends(get_current_admin),
):
    tc = db.get(TestCase, testcase_id)
    if tc is None:
        raise HTTPException(status_code=404, detail="测试案例不存在")
    problem = db.get(Problem, tc.problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return service.update_testcase(db, problem.week_id, problem.stable_id, testcase_id, payload)


@router.delete("/testcases/{testcase_id}", status_code=204)
def delete_testcase(testcase_id: int, db: Session = Depends(get_db), username: str = Depends(get_current_admin)):
    tc = db.get(TestCase, testcase_id)
    if tc is None:
        raise HTTPException(status_code=404, detail="测试案例不存在")
    problem = db.get(Problem, tc.problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    service.delete_testcase(db, problem.week_id, problem.stable_id, testcase_id)


@router.post(
    "/weeks/{week_id}/problems/{problem_stable_id}/testcases/import-json",
    response_model=TestCaseImportResult,
)
def import_cases_json(
    week_id: int,
    problem_stable_id: int,
    payload: TestCaseImportRequest,
    db: Session = Depends(get_db),
    username: str = Depends(get_current_admin),
):
    count = service.import_cases_json(
        db,
        week_id,
        problem_stable_id,
        payload.cases,
        payload.public_default,
    )
    return {"imported": count}


@router.post(
    "/weeks/{week_id}/problems/{problem_stable_id}/testcases/import-zip",
    response_model=TestCaseImportResult,
)
async def import_cases_zip(
    week_id: int,
    problem_stable_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    username: str = Depends(get_current_admin),
):
    from ..services.zip_import import MAX_ZIP_BYTES, import_zip_testcases

    content = await file.read(MAX_ZIP_BYTES + 1)
    if len(content) > MAX_ZIP_BYTES:
        raise HTTPException(status_code=400, detail="ZIP 文件过大（最大 10 MB）")
    return import_zip_testcases(db, week_id, problem_stable_id, content)


# ---------------- solution ----------------
@router.get("/weeks/{week_id}/problems/{problem_stable_id}/solution", response_model=SolutionOut)
def get_solution(week_id: int, problem_stable_id: int, db: Session = Depends(get_db), username: str = Depends(get_current_admin)):
    return service.get_solution(db, week_id, problem_stable_id)


@router.put("/weeks/{week_id}/problems/{problem_stable_id}/solution", response_model=SolutionOut)
def upsert_solution(
    week_id: int,
    problem_stable_id: int,
    payload: SolutionUpsert,
    db: Session = Depends(get_db),
    username: str = Depends(get_current_admin),
):
    return service.upsert_solution(db, week_id, problem_stable_id, payload.code)


@router.post("/weeks/{week_id}/problems/{problem_stable_id}/solution/verify")
async def verify_solution(week_id: int, problem_stable_id: int, request: Request, db: Session = Depends(get_db), username: str = Depends(get_current_admin)):
    from ..services.rate_limit import get_admin_verify_limiter
    limiter = get_admin_verify_limiter()
    async def _task():
        return await service.verify_solution(db, week_id, problem_stable_id)
    return await limiter.run(request, "admin:" + username, _task)


# ---------------- preview runs ----------------
@router.post("/weeks/{week_id}/preview/run-sample")
async def preview_run_sample(
    week_id: int,
    payload: PreviewRunSampleRequest,
    db: Session = Depends(get_db),
    username: str = Depends(get_current_admin),
):
    return await service.run_preview_sample(db, week_id, payload.problem_id, payload.code, payload.sample_index)


@router.post("/weeks/{week_id}/preview/run-custom")
async def preview_run_custom(
    week_id: int,
    payload: PreviewRunCustomRequest,
    db: Session = Depends(get_db),
    username: str = Depends(get_current_admin),
):
    return await service.run_preview_custom(db, week_id, payload.problem_id, payload.code, payload.input)


@router.post("/weeks/{week_id}/preview/run-all")
async def preview_run_all(
    week_id: int,
    payload: PreviewRunAllRequest,
    db: Session = Depends(get_db),
    username: str = Depends(get_current_admin),
):
    return await service.run_preview_all(db, week_id, payload.problem_id, payload.code)


# ---------------- snapshots ----------------
@router.get("/weeks/{week_id}/snapshots", response_model=list[SnapshotOut])
def list_snapshots(week_id: int, db: Session = Depends(get_db), username: str = Depends(get_current_admin)):
    return service.list_snapshots(db, week_id)


@router.post("/weeks/{week_id}/snapshots/{snapshot_id}/rollback", response_model=WeekOut)
def rollback_snapshot(week_id: int, snapshot_id: int, db: Session = Depends(get_db), username: str = Depends(get_current_admin)):
    return service.rollback_snapshot(db, week_id, snapshot_id)


# ---------------- legacy import ----------------
@router.post("/import-legacy", response_model=ImportReport)
def import_legacy(payload: ImportLegacyRequest, db: Session = Depends(get_db), username: str = Depends(get_current_admin)):
    return import_legacy_json(db, payload.path, payload.dry_run)
