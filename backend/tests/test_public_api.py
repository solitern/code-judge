from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Problem, TestCase as JudgeTestCase, Week, WeekNotice


def _make_week(db, status="PUBLISHED", publish_at=None):
    week = Week(week=20, title="第二十周", status=status, publish_at=publish_at)
    db.add(week)
    db.flush()
    p = Problem(week_id=week.id, stable_id=1, title="A+B", description="desc", input_format="x", output_format="y", template="int main(){return 0;}")
    db.add(p)
    db.flush()
    db.add(JudgeTestCase(problem_id=p.id, is_public=True, input_text="1 2", expected_output="3", sort_order=0, enabled=True))
    db.add(JudgeTestCase(problem_id=p.id, is_public=False, input_text="secret-input", expected_output="secret-output", sort_order=1, enabled=True))
    db.commit()
    return week.id, p.id


def test_current_week_public_does_not_include_hidden(client):
    from app.db import SessionLocal
    db = SessionLocal()
    _make_week(db, "PUBLISHED", datetime.now(timezone.utc) - timedelta(hours=1))
    db.close()
    r = client.get("/api/public/weeks/current")
    assert r.status_code == 200
    data = r.json()
    assert data["week"] == 20
    samples = data["problems"][0]["samples"]
    assert len(samples) == 1
    assert samples[0]["input"] == "1 2"
    # No hidden content anywhere.
    body = r.text
    assert "secret-input" not in body and "secret-output" not in body


def test_current_week_includes_markdown_notice(client):
    from app.db import SessionLocal

    db = SessionLocal()
    week_id, _ = _make_week(db, "PUBLISHED", datetime.now(timezone.utc) - timedelta(hours=1))
    notice = "**请注意：** [提交源文件](https://example.com/submit)"
    db.add(WeekNotice(week_id=week_id, content=notice))
    db.commit()
    db.close()

    response = client.get("/api/public/weeks/current")
    assert response.status_code == 200
    assert response.json()["notice"] == notice


def test_public_week_list_only_includes_released_weeks_in_descending_order(client):
    from app.db import SessionLocal
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    _make_week(db, "PUBLISHED", now - timedelta(hours=2))
    released = Week(week=18, title="第十八周", status="SCHEDULED", publish_at=now - timedelta(hours=1))
    future = Week(week=21, title="未来周次", status="SCHEDULED", publish_at=now + timedelta(hours=1))
    draft = Week(week=19, title="草稿周次", status="DRAFT", publish_at=None)
    db.add_all([released, future, draft])
    db.flush()
    db.add(Problem(week_id=released.id, stable_id=1, title="往期题目"))
    db.commit()
    released_id = released.id
    released_publish_at = released.publish_at.isoformat().replace("+00:00", "Z")
    db.close()

    response = client.get("/api/public/weeks")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert [item["week"] for item in data] == [20, 18]
    assert data[1] == {
        "id": released_id,
        "week": 18,
        "title": "第十八周",
        "problem_count": 1,
        "publish_at": released_publish_at,
    }
    assert "未来周次" not in response.text
    assert "草稿周次" not in response.text
    assert "往期题目" not in response.text

    db = SessionLocal()
    assert db.get(Week, released_id).status == "PUBLISHED"
    db.close()


def test_public_week_404_does_not_leak_draft(client):
    from app.db import SessionLocal
    db = SessionLocal()
    week = Week(week=21, title="草稿", status="DRAFT", publish_at=None)
    db.add(week)
    db.commit()
    wid = week.id
    db.close()
    r = client.get(f"/api/public/weeks/{wid}")
    assert r.status_code == 404
    r2 = client.get("/api/public/weeks/9999")
    assert r2.status_code == 404
    # Same response body shape for draft and nonexistent.
    assert r.json() == r2.json()


def test_scheduled_week_appears_after_publish_at(client):
    from app.db import SessionLocal
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    # Not yet published.
    wid, _ = _make_week(db, "SCHEDULED", now + timedelta(hours=1))
    db.close()
    assert client.get("/api/public/weeks/current").status_code == 200
    assert client.get("/api/public/weeks/current").json() is None
    # After publish_at.
    from app.db import SessionLocal as SL
    db = SL()
    week = db.get(Week, wid)
    week.publish_at = now - timedelta(seconds=5)
    db.commit()
    db.close()
    r = client.get("/api/public/weeks/current")
    assert r.status_code == 200
    assert r.json()["week"] == 20
    db = SL()
    published = db.get(Week, wid)
    assert published.status == "PUBLISHED"
    assert published.published_at == published.publish_at
    db.close()


def test_run_sample_success_calls_runner(client, monkeypatch):
    from app.db import SessionLocal
    db = SessionLocal()
    _make_week(db, "PUBLISHED", datetime.now(timezone.utc) - timedelta(hours=1))
    db.close()

    async def fake_call_runner(payload):
        return {
            "mode": "sample", "status": "ACCEPTED", "summary": "通过",
            "compiled": True, "compile_error": None, "passed_count": 1, "total_count": 1,
            "results": [{"case_id": 1, "passed": True, "status": "ACCEPTED", "time_ms": 1.0,
                         "input": "1 2", "expected": "3", "actual": "3", "stderr": None}],
        }

    import app.services.public as pub
    monkeypatch.setattr(pub, "call_runner", fake_call_runner)
    r = client.post("/api/public/run/sample", json={"week_id": 1, "problem_id": 1, "code": "int main(){}", "sample_index": 0})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ACCEPTED"


def test_run_closes_database_session_before_waiting_for_runner(client, monkeypatch):
    from app import db as db_module
    from app.api import public as public_api
    import app.services.public as pub

    with db_module.SessionLocal() as db:
        _make_week(db, "PUBLISHED", datetime.now(timezone.utc) - timedelta(hours=1))

    original_factory = db_module.SessionLocal
    session_closed = threading.Event()
    prepare_thread_ids: list[int] = []
    original_prepare = pub.prepare_sample

    class TrackingSessionContext:
        def __init__(self):
            self.db = original_factory()

        def __enter__(self):
            return self.db

        def __exit__(self, exc_type, exc, traceback):
            self.db.close()
            session_closed.set()

    def tracked_prepare(db, payload):
        prepare_thread_ids.append(threading.get_ident())
        return original_prepare(db, payload)

    async def fake_call_runner(payload):
        assert session_closed.is_set()
        assert prepare_thread_ids[0] != threading.get_ident()
        return {
            "mode": "sample", "status": "ACCEPTED", "summary": "通过",
            "compiled": True, "compile_error": None, "passed_count": 1, "total_count": 1,
            "results": [{"case_id": 1, "passed": True, "status": "ACCEPTED", "time_ms": 1.0,
                         "input": "1 2", "expected": "3", "actual": "3", "stderr": None}],
        }

    monkeypatch.setattr(public_api.db_module, "SessionLocal", TrackingSessionContext)
    monkeypatch.setattr(pub, "prepare_sample", tracked_prepare)
    monkeypatch.setattr(pub, "call_runner", fake_call_runner)

    response = client.post(
        "/api/public/run/sample",
        json={"week_id": 1, "problem_id": 1, "code": "int main(){}", "sample_index": 0},
    )

    assert response.status_code == 200
    assert session_closed.is_set()


def test_run_all_does_not_leak_hidden_cases(client, monkeypatch):
    from app.db import SessionLocal
    db = SessionLocal()
    _make_week(db, "PUBLISHED", datetime.now(timezone.utc) - timedelta(hours=1))
    db.close()

    async def fake_call_runner(payload):
        return {
            "mode": "all", "status": "WRONG_ANSWER", "summary": "未通过",
            "compiled": True, "compile_error": None, "passed_count": 0, "total_count": 2,
            "results": [
                {"case_id": 1, "passed": True, "status": "ACCEPTED", "time_ms": 1.0},
                {"case_id": 2, "passed": False, "status": "WRONG_ANSWER", "time_ms": 1.0},
            ],
        }

    import app.services.public as pub
    monkeypatch.setattr(pub, "call_runner", fake_call_runner)
    r = client.post("/api/public/run/all", json={"week_id": 1, "problem_id": 1, "code": "int main(){}"})
    assert r.status_code == 200
    body = r.text
    assert "secret-input" not in body and "secret-output" not in body


def test_public_api_never_returns_solution_code(client):
    from app.db import SessionLocal
    from app.models import Solution
    db = SessionLocal()
    _make_week(db, "PUBLISHED", datetime.now(timezone.utc) - timedelta(hours=1))
    week_id, problem_row_id = db.query(Week.id, __import__('app.models', fromlist=['Problem']).Problem.id).join(Problem).filter(Week.week == 20).one()
    sol = Solution(problem_id=problem_row_id, code="#include <stdio.h>\nint main(){return 0;}", verified=True)
    db.add(sol)
    db.commit()
    db.close()
    r = client.get("/api/public/weeks/current")
    assert r.status_code == 200
    assert "#include" not in r.text
