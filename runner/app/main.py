"""Judge Runner: internal FastAPI service.

This service is only reachable from the app container on a private Docker
network.  It compiles C code once per request and runs each test case in a
new restricted process.
"""
from __future__ import annotations

import logging
import math
import shutil
import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from .comparator import compare_output
from .compiler import compile_c
from .sandbox import RUNNER_TMP_ROOT, Limits, isolation_required, run_case, unshare_works

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("runner")

app = FastAPI(title="Judge Runner", docs_url=None, openapi_url=None, redoc_url=None)

MAX_SOURCE_BYTES = 64 * 1024
MAX_CASE_BYTES = 1024 * 1024
MAX_TEST_CASES = 20
MAX_COMPILE_TIMEOUT_MS = 10000
MAX_COMPILE_MEMORY_MB = 512


class CasePayload(BaseModel):
    input: str = Field(default="", max_length=MAX_CASE_BYTES)
    expected: str | None = Field(default=None, max_length=MAX_CASE_BYTES)


class LimitsPayload(BaseModel):
    compile_timeout_ms: int = Field(default=10000, ge=1000, le=30000)
    compile_memory_mb: int = Field(default=512, ge=64, le=1024)
    time_limit_ms: int = Field(default=2000, ge=100, le=30000)
    wall_time_ms: int = Field(default=5000, ge=500, le=60000)
    memory_limit_mb: int = Field(default=256, ge=16, le=1024)
    output_limit_kb: int = Field(default=1024, ge=16, le=10240)


class RunRequest(BaseModel):
    code: str = Field(min_length=1, max_length=MAX_SOURCE_BYTES)
    cases: list[CasePayload] = Field(default_factory=list, max_length=MAX_TEST_CASES)
    limits: LimitsPayload = Field(default_factory=LimitsPayload)
    mode: str = Field(default="all", pattern="^(sample|custom|all|verify)$")


class CaseResult(BaseModel):
    case_id: int
    passed: bool | None = None
    status: str
    time_ms: float | None = None
    memory_kb: float | None = None
    input: str | None = None
    expected: str | None = None
    actual: str | None = None
    stderr: str | None = None


class RunResponse(BaseModel):
    mode: str
    status: str
    summary: str
    compiled: bool
    compile_error: str | None = None
    passed_count: int = 0
    total_count: int = 0
    results: list[CaseResult] = []


@app.get("/health")
def health(response: Response):
    isolated = unshare_works()
    ready = isolated or not isolation_required()
    if not ready:
        response.status_code = 503
    return {
        "status": "ok" if ready else "isolation_unavailable",
        "gcc": bool(shutil.which("gcc")),
        "isolation": isolated,
    }


@app.post("/run", response_model=RunResponse)
def run_code(payload: RunRequest):
    if isolation_required() and not unshare_works():
        raise HTTPException(status_code=503, detail="安全隔离不可用，判题服务已拒绝执行代码")
    if not payload.cases:
        raise HTTPException(status_code=400, detail="测试案例不能为空")
    code = payload.code
    if len(code.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise HTTPException(status_code=400, detail="源码长度超出限制")
    for c in payload.cases:
        if len(c.input.encode("utf-8")) > MAX_CASE_BYTES:
            raise HTTPException(status_code=400, detail="测试案例输入长度超出限制")
        if c.expected is not None and len(c.expected.encode("utf-8")) > MAX_CASE_BYTES:
            raise HTTPException(status_code=400, detail="测试案例输出长度超出限制")

    lim = payload.limits
    limits = Limits(
        cpu_seconds=max(1, math.ceil(lim.time_limit_ms / 1000)),
        wall_seconds=max(1, math.ceil(lim.wall_time_ms / 1000)),
        memory_mb=lim.memory_limit_mb,
        output_kb=lim.output_limit_kb,
    )

    tmp_root = Path(RUNNER_TMP_ROOT)
    tmp_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="judge-", dir=str(tmp_root)))
    try:
        source_path = workdir / "main.c"
        binary_path = workdir / "main"
        source_path.write_text(code, encoding="utf-8")

        t0 = time.monotonic()
        ok, compile_error = compile_c(
            source_path,
            binary_path,
            limits,
            compile_timeout_ms=lim.compile_timeout_ms,
            compile_memory_mb=lim.compile_memory_mb,
        )
        compile_ms = int((time.monotonic() - t0) * 1000)
        if not ok:
            logger.info("compile error code_bytes=%d case_count=%d compile_ms=%d", len(code.encode("utf-8")), len(payload.cases), compile_ms)
            return RunResponse(
                mode=payload.mode,
                status="COMPILE_ERROR",
                summary="编译错误",
                compiled=False,
                compile_error=compile_error,
                total_count=len(payload.cases),
            )

        # One binary; each case is a fresh process.
        results: list[CaseResult] = []
        for idx, case in enumerate(payload.cases, start=1):
            r = run_case(binary_path, case.input, limits)
            if case.expected is not None:
                passed = r.status == "ACCEPTED" and compare_output(r.stdout, case.expected)
                final_status = "ACCEPTED" if passed else ("WRONG_ANSWER" if r.status == "ACCEPTED" else r.status)
            else:
                passed = None
                final_status = r.status
            results.append(CaseResult(
                case_id=idx,
                passed=passed,
                status=final_status,
                time_ms=r.time_ms,
                memory_kb=r.memory_kb,
                input=case.input if payload.mode in ("sample", "custom", "verify") else None,
                expected=case.expected if payload.mode in ("sample", "verify") else None,
                actual=r.stdout if payload.mode in ("sample", "custom", "verify") else None,
                stderr=r.stderr if payload.mode in ("sample", "custom", "verify") else None,
            ))

        passed_count = sum(1 for r in results if r.passed)
        if any(r.status == "COMPILE_ERROR" for r in results):
            overall = "COMPILE_ERROR"
        elif any(r.status == "SYSTEM_ERROR" for r in results):
            overall = "SYSTEM_ERROR"
        elif all(r.status == "ACCEPTED" for r in results):
            overall = "ACCEPTED"
        elif any(r.status == "TIME_LIMIT_EXCEEDED" for r in results):
            overall = "TIME_LIMIT_EXCEEDED"
        elif any(r.status == "MEMORY_LIMIT_EXCEEDED" for r in results):
            overall = "MEMORY_LIMIT_EXCEEDED"
        elif any(r.status == "OUTPUT_LIMIT_EXCEEDED" for r in results):
            overall = "OUTPUT_LIMIT_EXCEEDED"
        elif any(r.status == "RUNTIME_ERROR" for r in results):
            overall = "RUNTIME_ERROR"
        else:
            overall = "WRONG_ANSWER"
        summary = "全部通过" if overall == "ACCEPTED" else _summary_for(overall, passed_count, len(results))
        return RunResponse(
            mode=payload.mode,
            status=overall,
            summary=summary,
            compiled=True,
            passed_count=passed_count,
            total_count=len(results),
            results=results,
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _summary_for(status: str, passed: int, total: int) -> str:
    labels = {
        "WRONG_ANSWER": f"通过 {passed}/{total}",
        "COMPILE_ERROR": "编译错误",
        "RUNTIME_ERROR": "运行时错误",
        "TIME_LIMIT_EXCEEDED": "运行超时",
        "MEMORY_LIMIT_EXCEEDED": "内存超限",
        "OUTPUT_LIMIT_EXCEEDED": "输出超限",
        "SYSTEM_ERROR": "系统错误",
    }
    return labels.get(status, status)
