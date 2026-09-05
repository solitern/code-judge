"""Public API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import PublicWeek, PublicWeekSummary, RunAllRequest, RunCustomRequest, RunResponse, RunSampleRequest
from ..services import public as service

router = APIRouter(prefix="/public", tags=["public"])


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
async def run_sample(payload: RunSampleRequest, request: Request, db: Session = Depends(get_db)):
    return await service.run_sample(request, db, payload)


@router.post("/run/custom", response_model=RunResponse)
async def run_custom(payload: RunCustomRequest, request: Request, db: Session = Depends(get_db)):
    return await service.run_custom(request, db, payload)


@router.post("/run/all", response_model=RunResponse)
async def run_all(payload: RunAllRequest, request: Request, db: Session = Depends(get_db)):
    return await service.run_all(request, db, payload)
