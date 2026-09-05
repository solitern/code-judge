from __future__ import annotations

import app.db as db_module
from app.schemas import ProblemUpsert, WeekCreate, WeekUpdate
from app.services.admin import (
    create_week,
    list_snapshots,
    rollback_snapshot,
    update_week,
    upsert_problem,
)


def test_snapshot_and_rollback():
    db = db_module.SessionLocal()
    week = create_week(db, WeekCreate(week=40, title="快照测试"))
    wid = week.id
    p = upsert_problem(db, wid, 1, ProblemUpsert(stable_id=1, title="题目一", template="v1"))
    assert p.version == 1
    p = upsert_problem(db, wid, 1, ProblemUpsert(stable_id=1, title="题目一改", template="v2"))
    assert p.version == 2
    snaps = list_snapshots(db, wid)
    assert len(snaps) >= 2
    # Find the first snapshot that contains one problem (v2 after first save).
    target = next(s for s in snaps if s.version == 2)
    rolled = rollback_snapshot(db, wid, target.id)
    assert rolled.problem_count == 1
    db.close()


def test_snapshot_rollback_restores_week_notice():
    db = db_module.SessionLocal()
    week = create_week(db, WeekCreate(week=41, title="通知快照"))
    wid = week.id

    update_week(db, wid, WeekUpdate(notice="第一版通知"))
    update_week(db, wid, WeekUpdate(notice="第二版通知"))
    target = next(snapshot for snapshot in list_snapshots(db, wid) if snapshot.version == 2)

    rolled = rollback_snapshot(db, wid, target.id)
    assert rolled.notice == "第一版通知"
    db.close()
