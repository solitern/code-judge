"""Restricted process execution for student programs.

This sandbox is designed for Linux containers.  It enforces resource limits
through setrlimit and runs the child program as an unprivileged user.  When
the required tools are available, it creates user, network, mount and PID
namespaces for every test case.  The statically linked program is then
chrooted into its per-case directory, so it cannot inspect the runner
filesystem, sibling jobs or host processes.
"""
from __future__ import annotations

import logging
import os
import resource
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("runner.sandbox")

RUNNER_TMP_ROOT = Path(os.environ.get("RUNNER_TMP_ROOT", "/tmp/judge-runner"))
SANDBOX_LAUNCHER = Path(os.environ.get("RUNNER_SANDBOX_LAUNCHER", "/usr/local/bin/sandbox-launcher"))


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


def has_sandbox_launcher() -> bool:
    return SANDBOX_LAUNCHER.is_file() and os.access(SANDBOX_LAUNCHER, os.X_OK)


_unshare_works: bool | None = None


def unshare_works() -> bool:
    """Return True when the complete namespace + chroot chain is available."""
    global _unshare_works
    if _unshare_works is None:
        if not has_unshare() or not has_sandbox_launcher():
            _unshare_works = False
        else:
            try:
                proc = subprocess.run(
                    [
                        "unshare", "-U", "-r", "-n", "-m", "-p", "-f", "--",
                        str(SANDBOX_LAUNCHER), "/", "/bin/true", "32",
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

    # Keep the hard limit equal to the public limit. Student code may catch or
    # ignore SIGXCPU, but it cannot ignore the kernel's hard-limit SIGKILL.
    _try_set(resource.RLIMIT_CPU, limits.cpu_seconds, limits.cpu_seconds)
    _try_set(resource.RLIMIT_AS, limits.memory_mb * mb)
    # This is a defensive per-file limit. Standard output and error use pipes
    # and are counted cumulatively by the parent process below.
    _try_set(resource.RLIMIT_FSIZE, limits.output_kb * 1024)
    if set_nproc:
        _try_set(resource.RLIMIT_NPROC, limits.nproc)
    _try_set(resource.RLIMIT_NOFILE, limits.nofile)
    _try_set(resource.RLIMIT_STACK, 64 * mb)


def _decode_limited(data: bytearray, max_bytes: int) -> str:
    return bytes(data[:max_bytes]).decode("utf-8", errors="replace")


def run_case(
    binary_path: Path,
    input_text: str,
    limits: Limits,
) -> RunResult:
    """Run one compiled binary with one stdin in a fresh restricted process."""
    workdir = binary_path.parent
    run_id = f"{os.getpid()}_{int(time.time() * 1000000)}"
    case_dir = workdir / f"case_{run_id}"
    io_dir = workdir / f"io_{run_id}"
    case_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    io_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    stdin_path = io_dir / "stdin.txt"
    stdin_path.write_text(input_text, encoding="utf-8")

    # Give each execution its own root containing only the static binary.
    # Input is opened outside that root and output uses pipes, so no stream
    # files or container paths are visible inside the chroot.
    isolated = unshare_works()
    if isolated:
        case_binary = case_dir / "main"
        shutil.copy2(binary_path, case_binary)
        case_binary.chmod(0o700)
        cmd = [
            "unshare", "-U", "-r", "-n", "-m", "-p", "-f", "--",
            str(SANDBOX_LAUNCHER), ".", "/main", str(limits.nproc),
        ]
        child_cwd = str(case_dir)
    else:
        cmd = ["./main"]
        child_cwd = str(workdir)

    start = time.monotonic()
    proc: subprocess.Popen | None = None
    stdout_data = bytearray()
    stderr_data = bytearray()
    output_bytes = 0
    output_lock = threading.Lock()
    output_exceeded = threading.Event()
    reader_threads: list[threading.Thread] = []
    max_output_bytes = limits.output_kb * 1024

    def collect_output(stream, target: bytearray, keep_bytes: int) -> None:
        nonlocal output_bytes
        try:
            while chunk := os.read(stream.fileno(), 64 * 1024):
                with output_lock:
                    output_bytes += len(chunk)
                    remaining = max(0, keep_bytes - len(target))
                    target.extend(chunk[:remaining])
                    if output_bytes > max_output_bytes:
                        output_exceeded.set()
        finally:
            stream.close()

    def stop_process_group() -> None:
        if proc is None:
            return
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    try:
        with open(stdin_path, "rb") as fin:
            proc = subprocess.Popen(
                cmd,
                stdin=fin,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=child_cwd,
                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C"},
                # PID namespaces and the PID-1 supervisor require two forks.
                # The supervisor applies RLIMIT_NPROC only to the student.
                preexec_fn=lambda: _set_limits(limits, set_nproc=not isolated),
                close_fds=True,
            )
            assert proc.stdout is not None and proc.stderr is not None
            reader_threads = [
                threading.Thread(
                    target=collect_output,
                    args=(proc.stdout, stdout_data, max_output_bytes),
                    daemon=True,
                ),
                threading.Thread(
                    target=collect_output,
                    args=(proc.stderr, stderr_data, 64 * 1024),
                    daemon=True,
                ),
            ]
            for thread in reader_threads:
                thread.start()

            deadline = start + limits.wall_seconds
            status = None
            rusage = None
            forced_status = None
            while True:
                try:
                    pid, status, rusage = os.wait4(proc.pid, os.WNOHANG)
                    if pid != 0:
                        break
                except ChildProcessError:
                    break
                if output_exceeded.is_set():
                    forced_status = "OUTPUT_LIMIT_EXCEEDED"
                    stop_process_group()
                    try:
                        _, status, rusage = os.wait4(proc.pid, 0)
                    except ChildProcessError:
                        pass
                    break
                if time.monotonic() > deadline:
                    forced_status = "TIME_LIMIT_EXCEEDED"
                    stop_process_group()
                    try:
                        _, status, rusage = os.wait4(proc.pid, 0)
                    except ChildProcessError:
                        pass
                    break
                time.sleep(0.005)

            # Exiting PID 1 tears down the PID namespace. Drain both pipes only
            # after that point so late writes are included in the byte count.
            stop_process_group()
            for thread in reader_threads:
                thread.join(timeout=1)
            elapsed = (time.monotonic() - start) * 1000
            exit_code = os.waitstatus_to_exitcode(status) if status is not None else None
            proc.returncode = exit_code
            maxrss_kb = float(getattr(rusage, "ru_maxrss", 0)) if rusage is not None else 0.0
            with output_lock:
                stdout_text = _decode_limited(stdout_data, max_output_bytes)
                stderr_text = _decode_limited(stderr_data, 64 * 1024)

            if output_exceeded.is_set():
                return RunResult(status="OUTPUT_LIMIT_EXCEEDED", exit_code=exit_code,
                                 stdout=stdout_text, stderr=stderr_text,
                                 time_ms=elapsed, memory_kb=maxrss_kb)
            if forced_status is not None:
                return RunResult(status=forced_status, exit_code=exit_code,
                                 stdout=stdout_text, stderr=stderr_text,
                                 time_ms=elapsed, memory_kb=maxrss_kb)

            sig = None
            if exit_code is not None and exit_code < 0:
                sig = -exit_code
            elif isolated and exit_code is not None and 128 < exit_code <= 192:
                # The PID-1 launcher reports its child's terminating signal
                # using the conventional 128 + signal exit status.
                sig = exit_code - 128
            if sig is not None:
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
        stop_process_group()
        for thread in reader_threads:
            thread.join(timeout=0.1)
        shutil.rmtree(case_dir, ignore_errors=True)
        shutil.rmtree(io_dir, ignore_errors=True)
