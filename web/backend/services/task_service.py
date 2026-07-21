"""任务清单写入服务 - 管理员增改/停用 + 同级 task_code 自动顺移。"""
from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import ProjectProfile, StageMap, TaskDetail
from schemas import TaskCreate, TaskOut, TaskUpdate
from services.audit import log_action
from services.progress_service import recalculate_progress_percent

VALID_CRITICAL = frozenset({"🔴", "🟡", "🟢"})


class ConflictError(Exception):
    pass


def _snapshot(t: TaskDetail) -> dict:
    return {
        "task_id": t.task_id,
        "stage_id": t.stage_id,
        "task_name": t.task_name,
        "task_code": t.task_code,
        "seq": t.seq,
        "default_days": t.default_days,
        "critical_path": t.critical_path,
        "owner": t.owner,
        "description": t.description,
        "sort_order": t.sort_order,
        "is_active": t.is_active,
    }


def _sibling_index(code: str | None, parent_code: str) -> int | None:
    """若 code 是 parent 的直接子级（P.N），返回 N；否则 None。"""
    if not code:
        return None
    prefix = f"{parent_code}."
    if not code.startswith(prefix):
        return None
    rest = code[len(prefix) :]
    if not rest or "." in rest:
        return None
    if rest.isdigit():
        return int(rest)
    return None


def _list_siblings(db: Session, stage_id: int, parent_code: str) -> list[TaskDetail]:
    tasks = (
        db.execute(select(TaskDetail).where(TaskDetail.stage_id == stage_id))
        .scalars()
        .all()
    )
    siblings = [
        t for t in tasks if _sibling_index(t.task_code, parent_code) is not None
    ]
    siblings.sort(key=lambda t: _sibling_index(t.task_code, parent_code) or 0)
    return siblings


def _shift_sibling_codes(
    siblings: list[TaskDetail], parent_code: str, from_index: int
) -> None:
    """将末段序号 >= from_index 的同级任务整体 +1（从大到小，避免短暂撞码）。"""
    to_shift = [
        t
        for t in siblings
        if (_sibling_index(t.task_code, parent_code) or 0) >= from_index
    ]
    to_shift.sort(
        key=lambda t: _sibling_index(t.task_code, parent_code) or 0, reverse=True
    )
    for t in to_shift:
        n = _sibling_index(t.task_code, parent_code)
        assert n is not None
        t.task_code = f"{parent_code}.{n + 1}"
        t.seq = n + 1


def _recalc_all_progress(db: Session) -> None:
    for project in db.execute(select(ProjectProfile)).scalars().all():
        recalculate_progress_percent(db, project)


def create_task(
    db: Session,
    body: TaskCreate,
    actor: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> TaskOut:
    name = body.task_name.strip()
    owner = body.owner.strip()
    if not name or not owner:
        raise ValueError("任务名称与责任方不能为空")
    if body.critical_path not in VALID_CRITICAL:
        raise ValueError(f"无效关键路径标记: {body.critical_path}")
    if body.default_days < 0:
        raise ValueError("默认工期不能为负")

    stage = db.get(StageMap, body.stage_id)
    if not stage:
        raise ValueError("阶段不存在")

    parent_code: str
    if body.parent_task_id is None:
        parent_code = str(body.stage_id)
    else:
        parent = db.get(TaskDetail, body.parent_task_id)
        if not parent:
            raise ValueError("父任务不存在")
        if parent.stage_id != body.stage_id:
            raise ValueError("父任务不属于该阶段")
        if not parent.task_code:
            raise ValueError("父任务缺少 task_code")
        parent_code = parent.task_code

    siblings = _list_siblings(db, body.stage_id, parent_code)

    insert_at: int
    sort_anchor: int | None = None
    if body.insert_before_task_id is None:
        max_n = max((_sibling_index(t.task_code, parent_code) or 0) for t in siblings) if siblings else 0
        insert_at = max_n + 1
    else:
        before = db.get(TaskDetail, body.insert_before_task_id)
        if not before:
            raise ValueError("插入参照任务不存在")
        if before.stage_id != body.stage_id:
            raise ValueError("插入参照任务不属于该阶段")
        idx = _sibling_index(before.task_code, parent_code)
        if idx is None:
            raise ValueError("插入参照任务不是该父级下的同级任务")
        insert_at = idx
        sort_anchor = before.sort_order
        _shift_sibling_codes(siblings, parent_code, insert_at)

    if sort_anchor is not None:
        later = (
            db.execute(
                select(TaskDetail).where(
                    TaskDetail.stage_id == body.stage_id,
                    TaskDetail.sort_order >= sort_anchor,
                )
            )
            .scalars()
            .all()
        )
        # 从大到小 bump，避免唯一冲突（无唯一约束但保持稳定）
        later.sort(key=lambda t: t.sort_order, reverse=True)
        for t in later:
            t.sort_order += 1
        new_sort = sort_anchor
    else:
        max_sort = db.scalar(
            select(func.max(TaskDetail.sort_order)).where(
                TaskDetail.stage_id == body.stage_id
            )
        )
        new_sort = (max_sort or 0) + 1

    new_code = f"{parent_code}.{insert_at}"
    task = TaskDetail(
        stage_id=body.stage_id,
        task_name=name,
        task_code=new_code,
        seq=insert_at,
        default_days=body.default_days,
        critical_path=body.critical_path,
        owner=owner,
        description=body.description,
        sort_order=new_sort,
        is_active=1,
    )
    db.add(task)
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise ConflictError("同阶段下任务名称已存在") from e

    log_action(
        db,
        actor,
        "CREATE",
        "tasks",
        task.task_id,
        payload=_snapshot(task),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    _recalc_all_progress(db)
    db.commit()
    db.refresh(task)
    return TaskOut.model_validate(task)


def update_task(
    db: Session,
    task_id: int,
    body: TaskUpdate,
    actor: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> TaskOut:
    task = db.get(TaskDetail, task_id)
    if not task:
        raise LookupError("任务不存在")

    before = _snapshot(task)
    data = body.model_dump(exclude_unset=True)
    if "task_name" in data and data["task_name"] is not None:
        name = data["task_name"].strip()
        if not name:
            raise ValueError("任务名称不能为空")
        task.task_name = name
    if "owner" in data and data["owner"] is not None:
        owner = data["owner"].strip()
        if not owner:
            raise ValueError("责任方不能为空")
        task.owner = owner
    if "default_days" in data and data["default_days"] is not None:
        if data["default_days"] < 0:
            raise ValueError("默认工期不能为负")
        task.default_days = data["default_days"]
    if "critical_path" in data and data["critical_path"] is not None:
        if data["critical_path"] not in VALID_CRITICAL:
            raise ValueError(f"无效关键路径标记: {data['critical_path']}")
        task.critical_path = data["critical_path"]
    if "description" in data:
        task.description = data["description"]

    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise ConflictError("同阶段下任务名称已存在") from e

    log_action(
        db,
        actor,
        "UPDATE",
        "tasks",
        task.task_id,
        payload={"before": before, "after": _snapshot(task)},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(task)
    return TaskOut.model_validate(task)


def set_task_active(
    db: Session,
    task_id: int,
    active: bool,
    actor: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> TaskOut:
    task = db.get(TaskDetail, task_id)
    if not task:
        raise LookupError("任务不存在")

    before = _snapshot(task)
    task.is_active = 1 if active else 0
    log_action(
        db,
        actor,
        "UPDATE",
        "tasks",
        task.task_id,
        payload={
            "before": before,
            "after": _snapshot(task),
            "action": "activate" if active else "deactivate",
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )
    _recalc_all_progress(db)
    db.commit()
    db.refresh(task)
    return TaskOut.model_validate(task)


# 供测试/调试：避免未使用 import 告警
_ = re
