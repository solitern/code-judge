from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.compiler import compile_c
from app.sandbox import Limits, run_case

WORKDIR = Path(os.environ.get("RUNNER_TEST_TMP", "/tmp/runner-tests"))


def _compile(code: str, name: str) -> tuple[Path, Path]:
    work = WORKDIR / name
    work.mkdir(parents=True, exist_ok=True)
    src = work / "main.c"
    binary = work / "main"
    src.write_text(code, encoding="utf-8")
    limits = Limits(cpu_seconds=2, wall_seconds=4, memory_mb=256, output_kb=1024)
    ok, err = compile_c(src, binary, limits)
    assert ok, err
    return work, binary


def test_hello_world_compiles_and_runs():
    work, binary = _compile("#include <stdio.h>\nint main(){printf(\"hello\\n\");return 0;}", "hello")
    r = run_case(binary, "", Limits(cpu_seconds=1, wall_seconds=3, memory_mb=128, output_kb=64))
    assert r.status == "ACCEPTED", r.stderr
    assert r.stdout == "hello\n"
    # Binary exists and was created once; no .c recompilation happened here.


def test_multi_case_fresh_process_each_case():
    code = """#include <stdio.h>
int g = 0;
int main(){
    g++;
    printf("%d\\n", g);
    return 0;
}
"""
    work, binary = _compile(code, "fresh-process")
    limits = Limits(cpu_seconds=1, wall_seconds=3, memory_mb=128, output_kb=64)
    r1 = run_case(binary, "", limits)
    r2 = run_case(binary, "", limits)
    # If the same process were reused, the second run would print 2.
    assert r1.stdout.strip() == "1"
    assert r2.stdout.strip() == "1"


def test_compile_error():
    from app.compiler import compile_c
    work = WORKDIR / "compile-error"
    work.mkdir(parents=True, exist_ok=True)
    src = work / "main.c"
    src.write_text("int main(void) { return 0 }", encoding="utf-8")
    ok, err = compile_c(src, work / "main", Limits(cpu_seconds=2, wall_seconds=5, memory_mb=256, output_kb=64))
    assert not ok
    assert "error" in err.lower() or "错误" in err
    assert "main.c:" in err
    assert str(work) not in err


def test_compile_error_sanitizer_removes_runner_workdir():
    from app.compiler import _sanitize_compiler_output

    workdir = Path("/tmp/judge-runner/judge-abcd1234")
    output = f"{workdir}/main.c:3:5: error: expected expression"

    sanitized = _sanitize_compiler_output(output, workdir)

    assert sanitized == "main.c:3:5: error: expected expression"
    assert "/tmp/judge-runner" not in sanitized


def test_runtime_error():
    work, binary = _compile(
        '#include <stdio.h>\nint main(){ fprintf(stderr, "diagnostic\\n"); return 7; }',
        "runtime-error",
    )
    r = run_case(binary, "", Limits(cpu_seconds=1, wall_seconds=3, memory_mb=128, output_kb=64))
    assert r.status == "RUNTIME_ERROR"
    assert r.exit_code == 7
    assert r.stderr == "diagnostic\n"


def test_infinite_loop_timeout():
    work, binary = _compile("int main(){ while(1){} return 0; }", "tle")
    r = run_case(binary, "", Limits(cpu_seconds=1, wall_seconds=2, memory_mb=128, output_kb=64))
    assert r.status == "TIME_LIMIT_EXCEEDED", r.status


def test_output_limit_exceeded():
    work, binary = _compile("#include <stdio.h>\nint main(){ while(1){ printf(\"x\"); } }", "ole")
    r = run_case(binary, "", Limits(cpu_seconds=2, wall_seconds=5, memory_mb=128, output_kb=32))
    assert r.status == "OUTPUT_LIMIT_EXCEEDED"


def test_cpu_limit_applies_to_student_process_inside_pid_namespace():
    work, binary = _compile(
        """#include <time.h>
int main(void) {
    clock_t begin = clock();
    while ((double)(clock() - begin) / CLOCKS_PER_SEC < 1.5) {}
    return 0;
}
""",
        "cpu-limit",
    )
    result = run_case(binary, "", Limits(cpu_seconds=1, wall_seconds=3, memory_mb=128, output_kb=64))
    assert result.status == "TIME_LIMIT_EXCEEDED", result


def test_cpu_limit_cannot_be_ignored():
    work, binary = _compile(
        """#include <signal.h>
#include <time.h>
int main(void) {
    signal(SIGXCPU, SIG_IGN);
    clock_t begin = clock();
    while ((double)(clock() - begin) / CLOCKS_PER_SEC < 1.5) {}
    return 0;
}
""",
        "ignored-cpu-signal",
    )
    result = run_case(binary, "", Limits(cpu_seconds=1, wall_seconds=3, memory_mb=128, output_kb=64))
    assert result.status == "TIME_LIMIT_EXCEEDED", result
    assert result.time_ms is not None and result.time_ms < 1800, result


def test_output_limit_is_detected_when_sigxfsz_is_ignored():
    work, binary = _compile(
        """#include <signal.h>
#include <stdio.h>
int main(void) {
    signal(SIGXFSZ, SIG_IGN);
    for (int i = 0; i < 100000; ++i) putchar('x');
    return 0;
}
""",
        "ignored-output-signal",
    )
    result = run_case(binary, "", Limits(cpu_seconds=2, wall_seconds=3, memory_mb=128, output_kb=16))
    assert result.status == "OUTPUT_LIMIT_EXCEEDED", result
    assert len(result.stdout.encode("utf-8")) <= 16 * 1024


def test_output_limit_uses_a_non_rewindable_stream():
    work, binary = _compile(
        """#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <unistd.h>
int main(void) {
    for (int block = 0; block < 100; ++block) {
        ftruncate(STDOUT_FILENO, 0);
        lseek(STDOUT_FILENO, 0, SEEK_SET);
        for (int i = 0; i < 1024; ++i) putchar('x');
        fflush(stdout);
    }
    return 0;
}
""",
        "rewound-output",
    )
    result = run_case(binary, "", Limits(cpu_seconds=2, wall_seconds=3, memory_mb=128, output_kb=16))
    assert result.status == "OUTPUT_LIMIT_EXCEEDED", result


def test_exact_output_limit_is_allowed_but_combined_streams_are_bounded():
    work, binary = _compile(
        """#include <stdio.h>
int main(void) {
    for (int i = 0; i < 16 * 1024; ++i) putchar('x');
    return 0;
}
""",
        "exact-output-limit",
    )
    limits = Limits(cpu_seconds=2, wall_seconds=3, memory_mb=128, output_kb=16)
    exact = run_case(binary, "", limits)
    assert exact.status == "ACCEPTED", exact
    assert len(exact.stdout.encode("utf-8")) == 16 * 1024

    work, binary = _compile(
        """#include <stdio.h>
int main(void) {
    for (int i = 0; i < 10 * 1024; ++i) putchar('x');
    for (int i = 0; i < 10 * 1024; ++i) fputc('e', stderr);
    return 0;
}
""",
        "combined-output-limit",
    )
    combined = run_case(binary, "", limits)
    assert combined.status == "OUTPUT_LIMIT_EXCEEDED", combined


def test_temp_dirs_cleaned_after_run():
    from app.sandbox import RUNNER_TMP_ROOT
    RUNNER_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    work = RUNNER_TMP_ROOT / "cleanup-compile"
    work.mkdir(parents=True, exist_ok=True)
    src = work / "main.c"
    binary = work / "main"
    src.write_text("int main(){return 0;}", encoding="utf-8")
    ok, _ = compile_c(src, binary, Limits(cpu_seconds=2, wall_seconds=5, memory_mb=256, output_kb=64))
    assert ok
    before = set(os.listdir(RUNNER_TMP_ROOT))
    r = run_case(binary, "", Limits(cpu_seconds=1, wall_seconds=3, memory_mb=128, output_kb=64))
    assert r.status == "ACCEPTED"
    after = set(os.listdir(RUNNER_TMP_ROOT))
    # No per-case directories should remain.
    assert "case_" not in " ".join(after)


def test_hidden_case_response_does_not_reveal_input_or_output():
    from app.main import app as runner_app
    from fastapi.testclient import TestClient
    code = "#include <stdio.h>\nint main(){printf(\"2\\n\");return 0;}"
    client = TestClient(runner_app)
    r = client.post("/run", json={
        "code": code,
        "mode": "all",
        "cases": [{"input": "secret-input", "expected": "1"}],
        "limits": {"time_limit_ms": 1000, "wall_time_ms": 3000, "memory_limit_mb": 128, "output_limit_kb": 64,
                   "compile_timeout_ms": 10000, "compile_memory_mb": 512},
    })
    assert r.status_code == 200
    body = r.text
    assert "secret-input" not in body
    # Actual output for hidden cases must not be exposed.
    assert "2\n" not in body
    data = r.json()
    assert data["results"][0]["input"] is None
    assert data["results"][0]["actual"] is None


def test_run_request_compiles_once_and_runs_each_case(monkeypatch):
    """POST /run must compile exactly once and run each case in a new process."""
    from fastapi.testclient import TestClient
    import app.main as runner_main

    compile_calls = []
    run_calls = []

    def fake_compile_c(source_path, binary_path, limits, compile_timeout_ms=10000, compile_memory_mb=512):
        compile_calls.append(str(binary_path))
        binary_path.write_text("fake")
        return True, ""

    def fake_run_case(binary_path, input_text, limits):
        run_calls.append(input_text)
        from app.sandbox import RunResult
        return RunResult(status="ACCEPTED", stdout=input_text, stderr="", time_ms=1.0, memory_kb=100)

    monkeypatch.setattr(runner_main, "compile_c", fake_compile_c)
    monkeypatch.setattr(runner_main, "run_case", fake_run_case)

    client = TestClient(runner_main.app)
    r = client.post("/run", json={
        "code": "int main(){return 0;}",
        "mode": "all",
        "cases": [{"input": "a", "expected": "a"}, {"input": "b", "expected": "b"}],
        "limits": {"time_limit_ms": 1000, "wall_time_ms": 3000, "memory_limit_mb": 128, "output_limit_kb": 64,
                   "compile_timeout_ms": 10000, "compile_memory_mb": 512},
    })
    assert r.status_code == 200
    assert r.json()["compiled"] is True
    assert len(compile_calls) == 1
    assert len(run_calls) == 2


def test_runner_fails_closed_when_required_isolation_is_unavailable(monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as runner_main

    monkeypatch.setenv("RUNNER_REQUIRE_ISOLATION", "true")
    monkeypatch.setattr(runner_main, "unshare_works", lambda: False)
    client = TestClient(runner_main.app)

    health = client.get("/health")
    assert health.status_code == 503
    assert health.json()["status"] == "isolation_unavailable"

    response = client.post("/run", json={
        "code": "int main(){return 0;}",
        "mode": "all",
        "cases": [{"input": "", "expected": ""}],
    })
    assert response.status_code == 503


def test_forked_children_are_killed_when_parent_exits():
    work, binary = _compile(
        """#include <stdio.h>
#include <sys/types.h>
#include <unistd.h>
int main(){
    pid_t pid = fork();
    if (pid == 0) {
        sleep(1);
        FILE *f = fopen("escaped-child.txt", "w");
        if (f) { fputs("escaped", f); fclose(f); }
        while(1){}
    }
    return 0;
}
""",
        "fork-cleanup",
    )
    marker = work / "escaped-child.txt"
    marker.unlink(missing_ok=True)
    result = run_case(binary, "", Limits(cpu_seconds=1, wall_seconds=2, memory_mb=128, output_kb=64))
    assert result.status == "ACCEPTED"
    time.sleep(1.2)
    assert not marker.exists()


def test_isolated_program_cannot_read_a_sibling_task_file():
    from app.sandbox import RUNNER_TMP_ROOT, unshare_works

    if not unshare_works():
        pytest.skip("full namespace isolation is unavailable on this host")

    sibling = RUNNER_TMP_ROOT / "sibling-secret"
    sibling.mkdir(mode=0o700, parents=True, exist_ok=True)
    secret = sibling / "secret.txt"
    secret.write_text("must-not-leak", encoding="utf-8")
    escaped_path = str(secret).replace("\\", "\\\\").replace('"', '\\"')
    code = f'''#define _GNU_SOURCE
#include <sched.h>
#include <stdio.h>
int main(void) {{
    FILE *f = fopen("{escaped_path}", "r");
    if (f) {{ fclose(f); puts("leaked"); return 1; }}
    puts("blocked");
    return 0;
}}
'''
    try:
        _, binary = _compile(code, "cross-task-read")
        result = run_case(binary, "", Limits(cpu_seconds=1, wall_seconds=3, memory_mb=128, output_kb=64))
        assert result.status == "ACCEPTED", result.stderr
        assert result.stdout == "blocked\n"
    finally:
        shutil.rmtree(sibling, ignore_errors=True)


def test_student_cannot_escape_by_chrooting_again():
    from app.sandbox import RUNNER_TMP_ROOT, unshare_works

    if not unshare_works():
        pytest.skip("full namespace isolation is unavailable on this host")

    sibling = RUNNER_TMP_ROOT / "chroot-escape-secret"
    sibling.mkdir(mode=0o700, parents=True, exist_ok=True)
    secret = sibling / "secret.txt"
    secret.write_text("must-not-leak", encoding="utf-8")
    escaped_path = str(secret).replace("\\", "\\\\").replace('"', '\\"')
    code = f'''#define _GNU_SOURCE
#include <sched.h>
#include <stdio.h>
#include <sys/stat.h>
#include <unistd.h>
int main(void) {{
    mkdir("inner", 0700);
    if (unshare(CLONE_NEWUSER) == 0 && chroot("inner") == 0) {{
        for (int i = 0; i < 64; ++i) chdir("..");
        if (chroot(".") == 0) {{
            FILE *f = fopen("{escaped_path}", "r");
            if (f) {{ fclose(f); puts("leaked"); return 1; }}
        }}
    }}
    puts("blocked");
    return 0;
}}
'''
    try:
        _, binary = _compile(code, "chroot-escape")
        result = run_case(binary, "", Limits(cpu_seconds=1, wall_seconds=3, memory_mb=128, output_kb=64))
        assert result.status == "ACCEPTED", result.stderr
        assert result.stdout == "blocked\n"
    finally:
        shutil.rmtree(sibling, ignore_errors=True)


def test_pid_namespace_kills_children_that_detach_from_process_group(monkeypatch):
    import app.sandbox as sandbox

    if not sandbox.unshare_works():
        pytest.skip("full namespace isolation is unavailable on this host")

    work, binary = _compile(
        """#include <stdio.h>
#include <sys/types.h>
#include <unistd.h>
int main(void) {
    pid_t pid = fork();
    if (pid < 0) return 2;
    if (pid == 0) {
        setsid();
        sleep(1);
        FILE *f = fopen("escaped-child.txt", "w");
        if (f) { fputs("escaped", f); fclose(f); }
        while (1) {}
    }
    return 0;
}
""",
        "pid-namespace-cleanup",
    )
    original_rmtree = sandbox.shutil.rmtree
    monkeypatch.setattr(sandbox.shutil, "rmtree", lambda *args, **kwargs: None)
    try:
        result = run_case(binary, "", Limits(cpu_seconds=1, wall_seconds=2, memory_mb=128, output_kb=64))
        assert result.status == "ACCEPTED", result.stderr
        time.sleep(1.2)
        case_dirs = list(work.glob("case_*"))
        assert len(case_dirs) == 1
        assert not (case_dirs[0] / "escaped-child.txt").exists()
    finally:
        for leftover in (*work.glob("case_*"), *work.glob("io_*")):
            original_rmtree(leftover, ignore_errors=True)
