"""Health check routes."""
from __future__ import annotations

from fastapi import APIRouter

from ..config import get_settings
from ..services.runner_client import runner_health

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health():
    settings = get_settings()
    runner_status = await runner_health()
    return {
        "status": "ok",
        "runner": runner_status,
        "app": settings.app_name,
    }
