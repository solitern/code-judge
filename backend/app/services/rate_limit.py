"""In-memory concurrency and per-IP rate limiting for single-instance deployments."""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from collections import defaultdict, deque
from typing import TypeVar

T = TypeVar("T")

from fastapi import HTTPException, Request, status

from ..config import get_settings


class JudgeLimiter:
    """Simple semaphore + bounded queue + per-IP rate limit.

    Single-process only by design; Docker Compose runs one app instance.
    """

    def __init__(self, max_concurrency: int, queue_size: int, rate_per_minute: int) -> None:
        self.max_concurrency = max_concurrency
        self.queue_size = queue_size
        self.rate_per_minute = rate_per_minute
        self._semaphore = asyncio.Semaphore(max_concurrency)
        # Admission covers both running and queued jobs. Keeping it separate
        # prevents queue-capacity leaks when execution-slot acquisition times out.
        self._admission = asyncio.BoundedSemaphore(max_concurrency + queue_size)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def _check_rate(self, key: str) -> None:
        now = time.monotonic()
        async with self._lock:
            q = self._hits[key]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.rate_per_minute:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="运行过于频繁，请稍后再试")
            q.append(now)

    async def run(self, request: Request, key: str, task: Callable[[], Awaitable[T]]) -> T:
        await self._check_rate(key)
        try:
            await asyncio.wait_for(self._admission.acquire(), timeout=1)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="判题队列已满，请稍后再试")
        try:
            try:
                # Never wait forever: if the runner is stuck, return a clear error.
                await asyncio.wait_for(self._semaphore.acquire(), timeout=180)
            except asyncio.TimeoutError:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="判题服务繁忙，请稍后再试")
            try:
                return await task()
            finally:
                self._semaphore.release()
        finally:
            self._admission.release()


_limiter: JudgeLimiter | None = None
_admin_limiter: JudgeLimiter | None = None


def get_judge_limiter() -> JudgeLimiter:
    global _limiter
    if _limiter is None:
        settings = get_settings()
        _limiter = JudgeLimiter(
            settings.judge_max_concurrency,
            settings.judge_queue_size,
            settings.judge_rate_per_minute,
        )
    return _limiter


def get_admin_verify_limiter() -> JudgeLimiter:
    global _admin_limiter
    if _admin_limiter is None:
        settings = get_settings()
        _admin_limiter = JudgeLimiter(
            settings.admin_verify_max_concurrency,
            settings.judge_queue_size,
            settings.admin_verify_rate_per_minute,
        )
    return _admin_limiter


def client_ip(request: Request) -> str:
    settings = get_settings()
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"
