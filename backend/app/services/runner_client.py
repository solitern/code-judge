"""HTTP client for the internal Judge Runner service."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from ..config import get_settings

logger = logging.getLogger("app.runner_client")

_client: httpx.AsyncClient | None = None


def get_runner_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = httpx.AsyncClient(
            base_url=settings.runner_url,
            timeout=httpx.Timeout(180.0, connect=5.0),
        )
    return _client


async def call_runner(payload: dict[str, Any]) -> dict[str, Any]:
    """Send a judge request to the runner.  Never log source code."""
    client = get_runner_client()
    try:
        resp = await client.post("/run", json=payload)
    except httpx.HTTPError as exc:
        logger.warning("runner unreachable: %s", type(exc).__name__)
        raise RunnerUnavailable("判题服务暂时不可用，请稍后再试") from exc
    if resp.status_code >= 500:
        raise RunnerUnavailable("判题服务内部错误，请稍后再试")
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", "判题请求不合法")
        except Exception:
            detail = "判题请求不合法"
        raise RunnerUnavailable(str(detail))
    return resp.json()


async def close_runner_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def runner_health() -> str:
    client = get_runner_client()
    try:
        response = await client.get("/health", timeout=2.0)
        data = response.json()
        return str(data.get("status", "unknown"))
    except (httpx.HTTPError, ValueError):
        return "unreachable"


class RunnerUnavailable(Exception):
    pass
