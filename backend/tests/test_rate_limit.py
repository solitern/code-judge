from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.services.rate_limit import JudgeLimiter


@pytest.mark.asyncio
async def test_admission_capacity_is_released_when_slot_wait_times_out(monkeypatch):
    limiter = JudgeLimiter(max_concurrency=1, queue_size=1, rate_per_minute=100)
    await limiter._semaphore.acquire()

    real_wait_for = asyncio.wait_for

    async def short_wait(awaitable, timeout):
        if timeout == 180:
            timeout = 0.01
        return await real_wait_for(awaitable, timeout)

    monkeypatch.setattr(asyncio, "wait_for", short_wait)

    async def task():
        return "ok"

    with pytest.raises(HTTPException) as exc:
        await limiter.run(None, "client", task)
    assert exc.value.status_code == 503

    # If admission leaked, this acquire would time out because one running and
    # one leaked queued token would consume the full capacity.
    await real_wait_for(limiter._admission.acquire(), 0.1)
    limiter._admission.release()
    limiter._semaphore.release()
