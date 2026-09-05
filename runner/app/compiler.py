"""Compile C source code with GCC exactly once."""
from __future__ import annotations

import logging
import os
import signal
import subprocess
from pathlib import Path

from .sandbox import Limits, _set_limits

logger = logging.getLogger("runner.compiler")


def _sanitize_compiler_output(output: str, workdir: Path) -> str:
    """Remove the per-request working directory from diagnostics."""
    for prefix in {str(workdir), workdir.as_posix()}:
        output = output.replace(prefix + "/", "").replace(prefix + "\\", "")
    return output


def compile_c(
    source_path: Path,
    binary_path: Path,
    limits: Limits,
    compile_timeout_ms: int = 10000,
    compile_memory_mb: int = 512,
) -> tuple[bool, str]:
    compile_limits = Limits(
        cpu_seconds=max(limits.cpu_seconds, 10),
        wall_seconds=compile_timeout_ms // 1000 + 2,
        memory_mb=compile_memory_mb,
        output_kb=4096,
        nproc=128,
        nofile=64,
    )
    cmd = ["gcc", "-std=c11", "-O2", "-pipe", "-o", binary_path.name, source_path.name]
    stdout_file = binary_path.parent / "compile.out"
    stderr_file = binary_path.parent / "compile.err"
    try:
        with open(stdout_file, "wb") as out, open(stderr_file, "wb") as err:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                cwd=str(binary_path.parent),
                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C"},
                preexec_fn=lambda: _set_limits(compile_limits),
                close_fds=True,
            )
            try:
                proc.wait(timeout=compile_limits.wall_seconds)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
                return False, "编译超时"
        if proc.returncode != 0:
            stderr_text = stderr_file.read_text(encoding="utf-8", errors="replace")
            sanitized = _sanitize_compiler_output(stderr_text, binary_path.parent)
            return False, sanitized[:8000] or "编译失败"
        return True, ""
    except FileNotFoundError:
        return False, "GCC 未安装或不在 PATH 中"
    except Exception:
        logger.exception("compile failed")
        return False, "编译服务异常"
    finally:
        for f in (stdout_file, stderr_file):
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass
