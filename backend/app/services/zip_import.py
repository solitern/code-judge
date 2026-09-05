"""ZIP batch import for test cases.

Expected zip layout:
  problem-1/
    001.in
    001.out
    002.in
    002.out
    solution.c        (optional)

Rules:
  - .in and .out must be paired
  - file numbers must be unique
  - file size is limited
  - only UTF-8 text files
  - empty input/output is allowed for stdin but not for case content? We
    accept empty inputs and outputs because some problems legitimately use
    empty stdin or expect an empty line; however the zip entry count must
    match and the import is rejected when the zip is malformed.
"""
from __future__ import annotations

import io
import re
import zipfile

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Problem, Solution, TestCase, Week
MAX_ZIP_BYTES = 10 * 1024 * 1024


def import_zip_testcases(db: Session, week_id: int, problem_stable_id: int, content: bytes) -> dict:
    if len(content) > MAX_ZIP_BYTES:
        raise HTTPException(status_code=400, detail="ZIP 文件过大（最大 10 MB）")
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="无效的 ZIP 文件")

    settings = get_settings()
    infos = [i for i in zf.infolist() if not i.is_dir()]
    pairs: dict[str, dict] = {}
    solution_code = None
    seen_entries: set[tuple[str, str]] = set()

    for info in infos:
        name = info.filename
        if name.endswith("solution.c"):
            solution_code = _read_entry(zf, info, settings.max_source_bytes)
            continue
        m = re.match(r"(?:.*/)?([^/]+)\.(in|out)$", name)
        if not m:
            continue
        num = m.group(1)
        ext = m.group(2)
        entry_key = (num, ext)
        if entry_key in seen_entries:
            raise HTTPException(status_code=400, detail=f"文件重复: {num}.{ext}")
        seen_entries.add(entry_key)
        data = _read_entry(zf, info, settings.max_case_bytes)
        pairs.setdefault(num, {})[ext] = data

    if not pairs:
        raise HTTPException(status_code=400, detail="ZIP 中未找到 .in/.out 测试案例文件")

    week = db.get(Week, week_id)
    if week is None:
        raise HTTPException(status_code=404, detail="周次不存在")
    problem = next((p for p in week.problems if p.stable_id == problem_stable_id), None)
    if problem is None:
        problem = db.query(Problem).filter(Problem.week_id == week_id, Problem.stable_id == problem_stable_id).one_or_none()
    if problem is None:
        raise HTTPException(status_code=404, detail="题目不存在")

    if len(problem.testcases) + len(pairs) > settings.max_test_cases:
        raise HTTPException(status_code=400, detail=f"导入后测试案例不能超过 {settings.max_test_cases} 个")

    imported = 0
    max_sort = max([t.sort_order for t in problem.testcases], default=0)

    def sort_key(value: str) -> tuple[int, int | str]:
        return (0, int(value)) if value.isdigit() else (1, value)

    for idx, num in enumerate(sorted(pairs.keys(), key=sort_key)):
        pair = pairs[num]
        if "in" not in pair or "out" not in pair:
            raise HTTPException(status_code=400, detail=f"文件编号 {num} 的 .in/.out 不成对")
        input_text = pair["in"].decode("utf-8", errors="strict")
        output_text = pair["out"].decode("utf-8", errors="strict")
        db.add(TestCase(
            problem_id=problem.id,
            is_public=False,
            input_text=input_text,
            expected_output=output_text,
            sort_order=max_sort + idx + 1,
            enabled=True,
        ))
        imported += 1

    if solution_code is not None:
        sol = problem.solution
        if sol is None:
            sol = Solution(problem_id=problem.id, code=solution_code.decode("utf-8", errors="strict"))
            db.add(sol)
        else:
            sol.code = solution_code.decode("utf-8", errors="strict")
            sol.verified = False
            sol.last_verified_at = None

    problem.version = (problem.version or 0) + 1
    db.flush()
    # Keep ZIP imports consistent with every other testcase mutation: one
    # batch creates one recoverable version snapshot.
    from .admin import _save_snapshot

    _save_snapshot(db, week)
    db.commit()
    return {"imported": imported, "solution_imported": solution_code is not None}


def _read_entry(zf: zipfile.ZipFile, info: zipfile.ZipInfo, max_bytes: int) -> bytes:
    if info.file_size > max_bytes:
        raise HTTPException(status_code=400, detail=f"{info.filename} 文件大小超限")
    data = zf.read(info)
    if len(data) > max_bytes:
        raise HTTPException(status_code=400, detail=f"{info.filename} 文件大小超限")
    try:
        data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail=f"{info.filename} 不是合法 UTF-8 文本")
    return data
