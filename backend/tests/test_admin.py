from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timedelta, timezone

from app.db import SessionLocal
from app.models import Week


def _login(client):
    r = client.post("/api/admin/login", json={"username": "admin", "password": "test-password-123"})
    assert r.status_code == 200
    return {"X-CSRF-Token": r.json()["csrf_token"]}


def _create_problem(client, headers, week_number: int = 26) -> int:
    created = client.post(
        "/api/admin/weeks",
        json={"week": week_number, "title": "批量导入"},
        headers=headers,
    )
    assert created.status_code == 201
    week_id = created.json()["id"]
    problem = client.put(
        f"/api/admin/weeks/{week_id}/problems/1",
        json={
            "stable_id": 1,
            "title": "A + B",
            "description": "",
            "input_format": "",
            "output_format": "",
            "hint": "",
            "template": "",
            "time_limit_ms": 2000,
            "memory_limit_mb": 256,
            "output_limit_kb": 1024,
            "sort_order": 1,
        },
        headers=headers,
    )
    assert problem.status_code == 200
    return week_id


def test_login_sets_cookies_and_me_works(client):
    r = client.post("/api/admin/login", json={"username": "admin", "password": "test-password-123"})
    assert r.status_code == 200
    assert "admin_session" in r.cookies
    assert r.cookies["admin_session"]
    assert "csrf_token" in r.cookies
    r2 = client.get("/api/admin/me")
    assert r2.status_code == 200
    assert r2.json()["username"] == "admin"


def test_admin_mutation_requires_csrf(client):
    _login(client)
    r = client.post("/api/admin/weeks", json={"week": 20, "title": "x"})
    assert r.status_code == 403


def test_admin_can_create_week_and_preview(client):
    h = _login(client)
    r = client.post("/api/admin/weeks", json={"week": 20, "title": "第二十周"}, headers=h)
    assert r.status_code == 201
    week_id = r.json()["id"]
    r2 = client.get(f"/api/admin/weeks/{week_id}/preview")
    assert r2.status_code == 200
    assert r2.headers["cache-control"] == "no-store"
    assert r2.json()["is_preview"] is True


def test_public_cannot_access_draft(client):
    h = _login(client)
    r = client.post("/api/admin/weeks", json={"week": 21, "title": "草稿"}, headers=h)
    week_id = r.json()["id"]
    assert client.get(f"/api/public/weeks/{week_id}").status_code == 404


def test_schedule_and_immediate_publish(client):
    h = _login(client)
    r = client.post("/api/admin/weeks", json={"week": 22, "title": "定时"}, headers=h)
    week_id = r.json()["id"]
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    r = client.patch(f"/api/admin/weeks/{week_id}", json={"status": "SCHEDULED", "publish_at": future}, headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "SCHEDULED"
    r = client.patch(f"/api/admin/weeks/{week_id}", json={"status": "PUBLISHED"}, headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "PUBLISHED"
    publish_at = datetime.fromisoformat(r.json()["publish_at"].replace("Z", "+00:00"))
    assert publish_at < datetime.now(timezone.utc) + timedelta(seconds=1)
    public = client.get("/api/public/weeks/current")
    assert public.status_code == 200
    assert public.json()["id"] == week_id


def test_due_schedule_is_materialized_and_datetimes_are_utc(client):
    h = _login(client)
    created = client.post("/api/admin/weeks", json={"week": 29, "title": "到期发布"}, headers=h)
    week_id = created.json()["id"]

    import app.db as db_module

    with db_module.SessionLocal() as db:
        week = db.get(Week, week_id)
        week.status = "SCHEDULED"
        week.publish_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        db.commit()

    listed = client.get("/api/admin/weeks")
    assert listed.status_code == 200
    item = next(week for week in listed.json() if week["id"] == week_id)
    assert item["status"] == "PUBLISHED"
    assert item["published_at"] == item["publish_at"]
    assert item["publish_at"].endswith(("Z", "+00:00"))
    assert item["created_at"].endswith(("Z", "+00:00"))

    dashboard = client.get("/api/admin/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["scheduled_count"] == 0
    assert dashboard.json()["published_count"] == 1


def test_scheduling_does_not_create_large_content_snapshot(client):
    h = _login(client)
    created = client.post("/api/admin/weeks", json={"week": 30, "title": "轻量定时"}, headers=h)
    week_id = created.json()["id"]
    assert created.json()["version"] == 1

    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    scheduled = client.patch(
        f"/api/admin/weeks/{week_id}",
        json={"status": "SCHEDULED", "publish_at": future},
        headers=h,
    )
    assert scheduled.status_code == 200
    assert scheduled.json()["version"] == 1


def test_admin_can_save_validate_and_clear_week_notice(client):
    headers = _login(client)
    created = client.post(
        "/api/admin/weeks",
        json={"week": 28, "title": "通知测试"},
        headers=headers,
    )
    assert created.status_code == 201
    week_id = created.json()["id"]

    notice = "## 本周提交\n\n请通过 [WPS 表单](https://example.com/submit) 提交源文件。"
    saved = client.patch(
        f"/api/admin/weeks/{week_id}",
        json={"notice": notice},
        headers=headers,
    )
    assert saved.status_code == 200
    assert saved.json()["notice"] == notice

    fetched = client.get(f"/api/admin/weeks/{week_id}")
    assert fetched.status_code == 200
    assert fetched.json()["notice"] == notice

    too_long = client.patch(
        f"/api/admin/weeks/{week_id}",
        json={"notice": "x" * 20001},
        headers=headers,
    )
    assert too_long.status_code == 422
    assert client.get(f"/api/admin/weeks/{week_id}").json()["notice"] == notice

    cleared = client.patch(
        f"/api/admin/weeks/{week_id}",
        json={"notice": ""},
        headers=headers,
    )
    assert cleared.status_code == 200
    assert cleared.json()["notice"] == ""


def test_admin_can_update_week_title(client):
    headers = _login(client)
    created = client.post(
        "/api/admin/weeks",
        json={"week": 31, "title": "旧标题"},
        headers=headers,
    )
    week_id = created.json()["id"]

    updated = client.patch(
        f"/api/admin/weeks/{week_id}",
        json={"title": "实验 1（表）"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "实验 1（表）"
    assert client.get(f"/api/admin/weeks/{week_id}").json()["title"] == "实验 1（表）"


def test_admin_can_update_week_number_when_unused(client):
    headers = _login(client)
    first = client.post("/api/admin/weeks", json={"week": 45, "title": "原周次"}, headers=headers)
    occupied = client.post("/api/admin/weeks", json={"week": 46, "title": "已占用"}, headers=headers)
    assert first.status_code == 201
    assert occupied.status_code == 201
    week_id = first.json()["id"]

    same = client.patch(f"/api/admin/weeks/{week_id}", json={"week": 45, "title": "原周次"}, headers=headers)
    assert same.status_code == 200
    assert same.json()["week"] == 45

    conflict = client.patch(f"/api/admin/weeks/{week_id}", json={"week": 46}, headers=headers)
    assert conflict.status_code == 409
    assert client.get(f"/api/admin/weeks/{week_id}").json()["week"] == 45

    invalid = client.patch(f"/api/admin/weeks/{week_id}", json={"week": 0}, headers=headers)
    assert invalid.status_code == 422

    updated = client.patch(
        f"/api/admin/weeks/{week_id}",
        json={"week": 47, "title": "改号后"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["week"] == 47
    assert updated.json()["title"] == "改号后"
    assert client.get(f"/api/admin/weeks/{week_id}").json()["week"] == 47


def test_admin_can_import_a_complete_week_json(client):
    headers = _login(client)
    week_id = _create_problem(client, headers, week_number=32)
    old_case = client.post(
        f"/api/admin/weeks/{week_id}/problems/1/testcases",
        json={"input": "old", "output": "old", "is_public": False, "sort_order": 0, "enabled": True},
        headers=headers,
    )
    assert old_case.status_code == 201

    payload = {
        "week": 32,
        "title": "实验 1（表）",
        "problems": [
            {
                "id": 1,
                "title": "顺序表操作",
                "description": "描述一",
                "inputFormat": "输入一",
                "outputFormat": "输出一",
                "hint": "提示一",
                "template": "int main(void) { return 0; }",
                "samples": [{"input": "1\n", "output": "1\n", "explanation": "忽略该字段"}],
                "testCases": [{"input": "2\n", "output": "2\n"}],
            },
            {
                "id": 2,
                "title": "链表重排",
                "description": "描述二",
                "input_format": "输入二",
                "output_format": "输出二",
                "hint": "",
                "template": "",
                "time_limit_ms": 3000,
                "memory_limit_mb": 128,
                "output_limit_kb": 512,
                "sort_order": 5,
                "samples": [],
                "test_cases": [{"input": "3\n", "output": "3\n", "enabled": False}],
            },
        ],
    }
    imported = client.post(
        f"/api/admin/weeks/{week_id}/import-json",
        files={"file": ("week32.json", json.dumps(payload, ensure_ascii=False).encode(), "application/json")},
        headers=headers,
    )
    assert imported.status_code == 200
    assert imported.json() == {
        "title": "实验 1（表）",
        "problems_imported": 2,
        "samples_imported": 1,
        "hidden_cases_imported": 2,
        "solutions_imported": 0,
    }

    week = client.get(f"/api/admin/weeks/{week_id}").json()
    assert week["title"] == "实验 1（表）"
    assert week["version"] >= 2

    problems = client.get(f"/api/admin/weeks/{week_id}/problems").json()
    assert [(problem["stable_id"], problem["title"]) for problem in problems] == [
        (1, "顺序表操作"),
        (2, "链表重排"),
    ]
    assert problems[1]["sort_order"] == 5

    first_cases = client.get(f"/api/admin/weeks/{week_id}/problems/1/testcases").json()
    assert [(case["input"], case["is_public"]) for case in first_cases] == [
        ("1\n", True),
        ("2\n", False),
    ]
    second_cases = client.get(f"/api/admin/weeks/{week_id}/problems/2/testcases").json()
    assert len(second_cases) == 1
    assert second_cases[0]["enabled"] is False


def test_admin_can_import_week_json_with_standard_answer(client):
    headers = _login(client)
    week_id = _create_problem(client, headers, week_number=48)
    payload = {
        "week": 48,
        "title": "含标准答案",
        "problems": [
            {
                "id": 1,
                "title": "A + B",
                "template": "int main() { return 0; }",
                "samples": [{"input": "1 2\n", "output": "3\n"}],
                "testCases": [{"input": "3 4\n", "output": "7\n"}],
                "standard_answer": "#include <stdio.h>\nint main(){int a,b;scanf(\"%d%d\",&a,&b);printf(\"%d\\n\",a+b);}\n",
            },
            {
                "id": 2,
                "title": "无答案题",
                "samples": [{"input": "0\n", "output": "0\n"}],
            },
        ],
    }
    imported = client.post(
        f"/api/admin/weeks/{week_id}/import-json",
        files={"file": ("week48.json", json.dumps(payload).encode(), "application/json")},
        headers=headers,
    )
    assert imported.status_code == 200
    assert imported.json()["solutions_imported"] == 1

    first = client.get(f"/api/admin/weeks/{week_id}/problems/1/solution").json()
    assert "scanf" in first["code"]
    assert first["verified"] is False

    second = client.get(f"/api/admin/weeks/{week_id}/problems/2/solution").json()
    assert second["code"] == ""
    assert second["verified"] is False


def test_week_json_import_rejects_mismatched_week_without_changes(client):
    headers = _login(client)
    created = client.post(
        "/api/admin/weeks",
        json={"week": 33, "title": "保留标题"},
        headers=headers,
    )
    week_id = created.json()["id"]
    payload = {
        "week": 34,
        "title": "不应写入",
        "problems": [{"id": 1, "title": "不应写入"}],
    }

    response = client.post(
        f"/api/admin/weeks/{week_id}/import-json",
        files={"file": ("wrong-week.json", json.dumps(payload).encode(), "application/json")},
        headers=headers,
    )
    assert response.status_code == 400
    assert "当前页面是周次 33" in response.json()["detail"]
    assert client.get(f"/api/admin/weeks/{week_id}").json()["title"] == "保留标题"
    assert client.get(f"/api/admin/weeks/{week_id}/problems").json() == []


def test_dashboard_handles_sqlite_naive_publish_times(client):
    h = _login(client)
    created = client.post("/api/admin/weeks", json={"week": 23, "title": "面板时区"}, headers=h)
    week_id = created.json()["id"]
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    scheduled = client.patch(
        f"/api/admin/weeks/{week_id}",
        json={"status": "SCHEDULED", "publish_at": future},
        headers=h,
    )
    assert scheduled.status_code == 200

    # A new request/session loads SQLite DateTime values without tzinfo.
    dashboard = client.get("/api/admin/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["next_scheduled_publish"]["id"] == week_id


def test_duplicate_week_payload_is_validated(client):
    h = _login(client)
    created = client.post("/api/admin/weeks", json={"week": 24, "title": "源"}, headers=h)
    response = client.post(
        f"/api/admin/weeks/{created.json()['id']}/duplicate",
        json={"week": "not-a-number", "title": "副本"},
        headers=h,
    )
    assert response.status_code == 422


def test_admin_can_import_testcases_from_json_atomically(client):
    headers = _login(client)
    week_id = _create_problem(client, headers)
    url = f"/api/admin/weeks/{week_id}/problems/1/testcases/import-json"

    imported = client.post(
        url,
        json={
            "public_default": True,
            "cases": [
                {"in": "1 2\n", "expected": "3\n"},
                {"input": "5 8\n", "output": "13\n", "public": False, "enabled": False},
            ],
        },
        headers=headers,
    )
    assert imported.status_code == 200
    assert imported.json() == {"imported": 2, "solution_imported": False}

    listed = client.get(f"/api/admin/weeks/{week_id}/problems/1/testcases")
    assert listed.status_code == 200
    cases = listed.json()
    assert [(case["input"], case["output"]) for case in cases] == [
        ("1 2\n", "3\n"),
        ("5 8\n", "13\n"),
    ]
    assert cases[0]["is_public"] is True
    assert cases[1]["is_public"] is False
    assert cases[1]["enabled"] is False

    invalid = client.post(
        url,
        json={"cases": [{"input": "valid", "output": "valid"}, {"input": 42, "output": "bad"}]},
        headers=headers,
    )
    assert invalid.status_code == 422
    listed_again = client.get(f"/api/admin/weeks/{week_id}/problems/1/testcases")
    assert len(listed_again.json()) == 2


def test_admin_can_import_paired_zip_testcases(client):
    headers = _login(client)
    week_id = _create_problem(client, headers, week_number=27)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("cases/001.in", "2 3\n")
        zf.writestr("cases/001.out", "5\n")
        zf.writestr("cases/002.in", "8 13\n")
        zf.writestr("cases/002.out", "21\n")

    imported = client.post(
        f"/api/admin/weeks/{week_id}/problems/1/testcases/import-zip",
        files={"file": ("cases.zip", archive.getvalue(), "application/zip")},
        headers=headers,
    )
    assert imported.status_code == 200
    assert imported.json() == {"imported": 2, "solution_imported": False}

    cases = client.get(f"/api/admin/weeks/{week_id}/problems/1/testcases").json()
    assert [case["input"] for case in cases] == ["2 3\n", "8 13\n"]
    assert all(case["is_public"] is False for case in cases)


def test_csrf_origin_check_requires_exact_origin(client):
    from app.main import settings

    h = _login(client)
    previous = settings.allowed_origin
    settings.allowed_origin = "https://judge.example.com"
    try:
        response = client.post(
            "/api/admin/weeks",
            json={"week": 25, "title": "非法来源"},
            headers={**h, "Origin": "https://judge.example.com.attacker.invalid"},
        )
        assert response.status_code == 403

        response = client.post(
            "/api/admin/weeks",
            json={"week": 25, "title": "合法来源"},
            headers={**h, "Origin": "https://judge.example.com"},
        )
        assert response.status_code == 201
    finally:
        settings.allowed_origin = previous
