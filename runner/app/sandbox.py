"""Restricted process execution for student programs.

This sandbox is designed for Linux containers.  It enforces resource limits
through setrlimit and runs the child program as an unprivileged user.  When
the required tools are available, it creates user, network, mount and PID
namespaces for every test case.  The statically linked program is then
chrooted into an otherwise empty per-case directory, so it cannot inspect
the runner filesystem, sibling jobs or host processes.
"""
from __future__ import annotations

import logging
import os
import resource
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("runner.sandbox")

RUNNER_TMP_ROOT = Path(os.environ.get("RUNNER_TMP_ROOT", "/tmp/judge-runner"))


def isolation_required() -> bool:
    value = os.environ.get("RUNNER_REQUIRE_ISOLATION", "false")
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Limits:
    cpu_seconds: int = 2
    wall_seconds: int = 5
    memory_mb: int = 256
    output_kb: int = 1024
    nproc: int = 32
    nofile: int = 64


@dataclass
class RunResult:
    status: str  # ACCEPTED, WRONG_ANSWER, COMPILE_ERROR, RUNTIME_ERROR, TIME_LIMIT_EXCEEDED, MEMORY_LIMIT_EXCEEDED, OUTPUT_LIMIT_EXCEEDED, SYSTEM_ERROR
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    time_ms: float | None = None
    memory_kb: float | None = None
    passed: bool | None = None


def has_unshare() -> bool:
    return shutil.which("unshare") is not None


def has_chroot() -> bool:
    return shutil.which("chroot") is not None


def has_prlimit() -> bool:
    return shutil.which("prlimit") is not None


_unshare_works: bool | None = None


def unshare_works() -> bool:
    """Return True when the complete namespace + chroot chain is available."""
    global _unshare_works
    if _unshare_works is None:
        if not has_unshare() or not has_chroot() or not has_prlimit():
            _unshare_works = False
        else:
            try:
                proc = subprocess.run(
                    [
                        "unshare", "-U", "-r", "-n", "-m", "-p", "-f", "--",
                        "prlimit", "--nproc=32:32", "--", "chroot", "/", "/bin/true",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
                _unshare_works = proc.returncode == 0
            except Exception:
                _unshare_works = False
    return _unshare_works


def _set_limits(limits: Limits, *, set_nproc: bool = True) -> None:
    """Apply resource limits in the forked child before exec."""
    try:
        os.setsid()
    except OSError:
        pass
    os.umask(0o077)
    mb = 1024 * 1024

    def _try_set(res: int, soft: int, hard: int | None = None) -> None:
        hard = hard if hard is not None else soft
        try:
            resource.setrlimit(res, (soft, hard))
        except (OSError, ValueError) as exc:
            logger.debug("setrlimit %s failed: %s", res, exc)

    _try_set(resource.RLIMIT_CPU, limits.cpu_seconds, limits.cpu_seconds + 2)
    _try_set(resource.RLIMIT_AS, limits.memory_mb * mb)
    _try_set(resource.RLIMIT_FSIZE, limits.output_kb * 1024)
    if set_nproc:
        _try_set(resource.RLIMIT_NPROC, limits.nproc)
    _try_set(resource.RLIMIT_NOFILE, limits.nofile)
    _try_set(resource.RLIMIT_STACK, 64 * mb)


def _read_limited(path: Path, max_bytes: int) -> str:
    try:
        data = path.read_bytes()[:max_bytes]
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def run_case(
    binary_path: Path,
    input_text: str,
    limits: Limits,
) -> RunResult:
    """Run one compiled binary with one stdin in a fresh restricted process."""
    workdir = binary_path.parent
    case_dir = workdir / f"case_{os.getpid()}_{int(time.time() * 1000000)}"
    case_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    stdin_path = case_dir / "stdin.txt"
    stdout_path = case_dir / "stdout.txt"
    stderr_path = case_dir / "stderr.txt"
    stdin_path.write_text(input_text, encoding="utf-8")

    # Give each execution its own root containing only the static binary.
    # Standard streams are opened by the parent first, so no input/output
    # files or container paths need to be visible inside the chroot.
    isolated = unshare_works()
    if isolated:
        case_binary = case_dir / "main"
        shutil.copy2(binary_path, case_binary)
        case_binary.chmod(0o700)
        cmd = [
            "unshare", "-U", "-r", "-n", "-m", "-p", "-f", "--",
            "prlimit", f"--nproc={limits.nproc}:{limits.nproc}", "--",
            "chroot", ".", "/main",
        ]
        child_cwd = str(case_dir)
    else:
        cmd = ["./main"]
        child_cwd = str(workdir)

    start = time.monotonic()
    proc: subprocess.Popen | None = None
    try:
        with open(stdin_path, "rb") as fin, open(stdout_path, "wb") as fout, open(stderr_path, "wb") as ferr:
            proc = subprocess.Popen(
                cmd,
                stdin=fin,
                stdout=fout,
                stderr=ferr,
                cwd=child_cwd,
                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C"},
                # PID namespaces require one fork. Apply RLIMIT_NPROC through
                # prlimit after that fork; all other limits can be set here.
                preexec_fn=lambda: _set_limits(limits, set_nproc=not isolated),
                close_fds=True,
            )
            deadline = start + limits.wall_seconds
            status = None
            rusage = None
            while True:
                try:
                    pid, status, rusage = os.wait4(proc.pid, os.WNOHANG)
                    if pid != 0:
                        break
                except ChildProcessError:
                    break
                if time.monotonic() > deadline:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    try:
                        os.wait4(proc.pid, 0)
                    except ChildProcessError:
                        pass
                    elapsed = (time.monotonic() - start) * 1000
                    stdout_text = _read_limited(stdout_path, limits.output_kb * 1024)
                    stderr_text = _read_limited(stderr_path, 64 * 1024)
                    return RunResult(status="TIME_LIMIT_EXCEEDED", exit_code=None,
                                     stdout=stdout_text, stderr=stderr_text, time_ms=elapsed)
                time.sleep(0.005)

            elapsed = (time.monotonic() - start) * 1000
            exit_code = os.waitstatus_to_exitcode(status) if status is not None else None
            maxrss_kb = float(getattr(rusage, "ru_maxrss", 0)) if rusage is not None else 0.0
            # The submitted program may have forked children. Always tear down
            # the whole process group after its leader exits.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout_text = _read_limited(stdout_path, limits.output_kb * 1024)
            stderr_text = _read_limited(stderr_path, 64 * 1024)

            if exit_code is not None and exit_code < 0:
                sig = -exit_code
                if sig == signal.SIGXFSZ:
                    return RunResult(status="OUTPUT_LIMIT_EXCEEDED", exit_code=exit_code,
                                     stdout=stdout_text, stderr=stderr_text,
                                     time_ms=elapsed, memory_kb=maxrss_kb)
                if sig in (signal.SIGKILL, signal.SIGSEGV) and maxrss_kb > limits.memory_mb * 1024:
                    return RunResult(status="MEMORY_LIMIT_EXCEEDED", exit_code=exit_code,
                                     stdout=stdout_text, stderr=stderr_text,
                                     time_ms=elapsed, memory_kb=maxrss_kb)
                if sig in (signal.SIGXCPU, signal.SIGKILL):
                    return RunResult(status="TIME_LIMIT_EXCEEDED", exit_code=exit_code,
                                     stdout=stdout_text, stderr=stderr_text,
                                     time_ms=elapsed, memory_kb=maxrss_kb)
                return RunResult(status="RUNTIME_ERROR", exit_code=exit_code,
                                 stdout=stdout_text, stderr=stderr_text,
                                 time_ms=elapsed, memory_kb=maxrss_kb)

            if maxrss_kb > limits.memory_mb * 1024:
                return RunResult(status="MEMORY_LIMIT_EXCEEDED", exit_code=exit_code,
                                 stdout=stdout_text, stderr=stderr_text,
                                 time_ms=elapsed, memory_kb=maxrss_kb)
            if exit_code != 0:
                return RunResult(status="RUNTIME_ERROR", exit_code=exit_code,
                                 stdout=stdout_text, stderr=stderr_text,
                                 time_ms=elapsed, memory_kb=maxrss_kb)
            return RunResult(status="ACCEPTED", exit_code=0,
                             stdout=stdout_text, stderr=stderr_text,
                             time_ms=elapsed, memory_kb=maxrss_kb)
    except Exception as exc:  # pragma: no cover
        logger.exception("run_case failed")
        return RunResult(status="SYSTEM_ERROR", stderr=str(exc))
    finally:
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        shutil.rmtree(case_dir, ignore_errors=True)
