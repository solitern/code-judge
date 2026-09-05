"""Public API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import db as db_module
from ..db import get_db
from ..schemas import PublicWeek, PublicWeekSummary, RunAllRequest, RunCustomRequest, RunResponse, RunSampleRequest
from ..services import public as service

router = APIRouter(prefix="/public", tags=["public"])


def _prepare_with_db(preparer, payload):
    """Run blocking ORM work in a worker thread and close it before queuing."""
    with db_module.SessionLocal() as db:
        return preparer(db, payload)


@router.get("/weeks", response_model=list[PublicWeekSummary])
def list_weeks(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return service.list_published_weeks(db)


@router.get("/weeks/current", response_model=PublicWeek | None)
def current_week(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return service.get_current_week(db)


@router.get("/weeks/{week_id}", response_model=PublicWeek)
def get_week(week_id: int, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return service.get_week_public(db, week_id)


@router.post("/run/sample", response_model=RunResponse)
async def run_sample(payload: RunSampleRequest, request: Request):
    prepared = await run_in_threadpool(_prepare_with_db, service.prepare_sample, payload)
    return await service.dispatch_judge(request, prepared)


@router.post("/run/custom", response_model=RunResponse)
async def run_custom(payload: RunCustomRequest, request: Request):
    prepared = await run_in_threadpool(_prepare_with_db, service.prepare_custom, payload)
    return await service.dispatch_judge(request, prepared)


@router.post("/run/all", response_model=RunResponse)
async def run_all(payload: RunAllRequest, request: Request):
    prepared = await run_in_threadpool(_prepare_with_db, service.prepare_all, payload)
    return await service.dispatch_judge(request, prepared)
