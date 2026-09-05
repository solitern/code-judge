from __future__ import annotations

import os
import sys
import time
from pathlib import Path

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
    assert r.status in ("OUTPUT_LIMIT_EXCEEDED", "TIME_LIMIT_EXCEEDED", "RUNTIME_ERROR")


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
