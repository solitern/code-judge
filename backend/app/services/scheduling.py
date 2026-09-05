"""Shared helpers for scheduled week publication and UTC datetimes."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import Week


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """Restore UTC information lost by SQLite's timezone-naive DateTime values."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def publish_due_weeks(db: Session) -> int:
    """Atomically turn every due SCHEDULED week into a PUBLISHED week.

    Public visibility used to be calculated only in queries, leaving the stored
    status stuck at SCHEDULED forever. The inexpensive read first avoids taking
    SQLite's writer lock on ordinary requests where nothing is due.
    """
    now = utcnow()
    due_ids = db.execute(
        select(Week.id).where(
            Week.status == "SCHEDULED",
            Week.publish_at.is_not(None),
            Week.publish_at <= now,
        )
    ).scalars().all()
    if not due_ids:
        return 0

    result = db.execute(
        update(Week)
        .where(Week.id.in_(due_ids), Week.status == "SCHEDULED")
        .values(status="PUBLISHED", published_at=Week.publish_at, archived_at=None)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return int(result.rowcount or 0)
