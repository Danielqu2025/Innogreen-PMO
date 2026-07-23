"""周进展日志服务 - L3 progress_journal"""
from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import ProgressJournal, ProjectProfile, TaskDetail
from schemas import JournalCreate, JournalOut, JournalUpdate
from services.audit import log_action

_WEEK_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ConflictError(Exception):
    pass


def _to_out(row: ProgressJournal, task: TaskDetail | None) -> JournalOut:
    return JournalOut(
        journal_id=row.journal_id,
        project_id=row.project_id,
        task_id=row.task_id,
        task_code=task.task_code if task else None,
        task_name=task.task_name if task else None,
        week_start=row.week_start,
        week_label=row.week_label,
        note=row.note,
        source=row.source,
        actor=row.actor,
        created_at=row.created_at,
    )


def list_journals(
    db: Session,
    project_id: int,
    *,
    task_id: int | None = None,
    limit: int = 100,
) -> list[JournalOut]:
    if not db.get(ProjectProfile, project_id):
        raise LookupError("企业不存在")
    limit = max(1, min(limit, 500))
    q = (
        select(ProgressJournal, TaskDetail)
        .outerjoin(TaskDetail, TaskDetail.task_id == ProgressJournal.task_id)
        .where(ProgressJournal.project_id == project_id)
        .order_by(ProgressJournal.week_start.desc(), ProgressJournal.journal_id.desc())
        .limit(limit)
    )
    if task_id is not None:
        q = q.where(ProgressJournal.task_id == task_id)
    rows = db.execute(q).all()
    return [_to_out(j, t) for j, t in rows]


def create_journal(
    db: Session,
    project_id: int,
    task_id: int,
    body: JournalCreate,
    actor: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> JournalOut:
    if not db.get(ProjectProfile, project_id):
        raise LookupError("企业不存在")
    task = db.get(TaskDetail, task_id)
    if not task:
        raise LookupError("任务不存在")
    if not task.is_active:
        raise ValueError("任务已停用，无法追加周记")

    week_start = body.week_start.strip()[:10]
    if not _WEEK_RE.match(week_start):
        raise ValueError("week_start 须为 YYYY-MM-DD")
    note = body.note.strip()
    if not note:
        raise ValueError("周记内容不能为空")

    row = ProgressJournal(
        project_id=project_id,
        task_id=task_id,
        week_start=week_start,
        week_label=body.week_label.strip() if body.week_label else None,
        note=note,
        source="web",
        actor=actor,
        created_at=datetime.now().isoformat(timespec="seconds"),
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise ConflictError("相同周次与正文已存在") from e

    log_action(
        db,
        actor,
        "CREATE",
        "journal",
        row.journal_id,
        payload={
            "project_id": project_id,
            "task_id": task_id,
            "week_start": week_start,
            "note": note[:200],
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(row)
    return _to_out(row, task)


def _get_journal_row(
    db: Session, project_id: int, task_id: int, journal_id: int
) -> ProgressJournal:
    if not db.get(ProjectProfile, project_id):
        raise LookupError("企业不存在")
    row = db.get(ProgressJournal, journal_id)
    if (
        not row
        or row.project_id != project_id
        or row.task_id != task_id
    ):
        raise LookupError("周记不存在")
    return row


def update_journal(
    db: Session,
    project_id: int,
    task_id: int,
    journal_id: int,
    body: JournalUpdate,
    actor: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> JournalOut:
    row = _get_journal_row(db, project_id, task_id, journal_id)
    task = db.get(TaskDetail, task_id) if task_id else None

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("未提供更新字段")

    before = {
        "week_start": row.week_start,
        "week_label": row.week_label,
        "note": row.note,
    }

    if "week_start" in updates and updates["week_start"] is not None:
        week_start = updates["week_start"].strip()[:10]
        if not _WEEK_RE.match(week_start):
            raise ValueError("week_start 须为 YYYY-MM-DD")
        row.week_start = week_start
    if "note" in updates and updates["note"] is not None:
        note = updates["note"].strip()
        if not note:
            raise ValueError("周记内容不能为空")
        row.note = note
    if "week_label" in updates:
        label = updates["week_label"]
        row.week_label = label.strip() if label else None

    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise ConflictError("相同周次与正文已存在") from e

    log_action(
        db,
        actor,
        "UPDATE",
        "journal",
        row.journal_id,
        payload={"before": before, "after": {
            "week_start": row.week_start,
            "week_label": row.week_label,
            "note": row.note[:200],
        }},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(row)
    return _to_out(row, task)


def delete_journal(
    db: Session,
    project_id: int,
    task_id: int,
    journal_id: int,
    actor: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    row = _get_journal_row(db, project_id, task_id, journal_id)
    payload = {
        "project_id": project_id,
        "task_id": task_id,
        "week_start": row.week_start,
        "note": row.note[:200],
    }
    db.delete(row)
    log_action(
        db,
        actor,
        "DELETE",
        "journal",
        journal_id,
        payload=payload,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.commit()
