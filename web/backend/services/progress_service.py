"""进度写入服务 - Phase C"""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import ProjectProfile, ProjectProgress, StageMap, TaskDetail
from schemas import ProgressOut, ProgressUpdate
from services.audit import log_progress_update

VALID_STATUSES = frozenset({"待开始", "进行中", "已完成", "已跳过", "卡点"})
# 已触达：出现这些状态的任务进度即视为该阶段有工作记录
STAGE_TOUCH_STATUSES = frozenset({"进行中", "已完成", "卡点", "已跳过"})
# 公用工程及服务类合同签定：可与主链并行，不作为「当前阶段」（stage_id=4）
AUTO_STAGE_EXCLUDE_IDS = frozenset({4})


def _progress_snapshot(row: ProjectProgress) -> dict:
    return {
        "status": row.status,
        "assigned_to": row.assigned_to,
        "blocker_note": row.blocker_note,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
        "planned_start": row.planned_start,
        "planned_end": row.planned_end,
        "vendor": row.vendor,
    }


def to_progress_out(row: ProjectProgress, task: TaskDetail) -> ProgressOut:
    return ProgressOut(
        progress_id=row.progress_id,
        project_id=row.project_id,
        task_id=row.task_id,
        task_code=task.task_code,
        task_name=task.task_name,
        stage_id=task.stage_id,
        status=row.status,
        assigned_to=row.assigned_to,
        started_at=row.started_at,
        completed_at=row.completed_at,
        planned_start=row.planned_start,
        planned_end=row.planned_end,
        vendor=row.vendor,
        blocker_note=row.blocker_note,
        critical_path=task.critical_path,
    )


def recalculate_progress_percent(db: Session, project: ProjectProfile) -> None:
    """已完成任务数 / 启用任务数 → progress_percent (0-100)。"""
    total_tasks = (
        db.scalar(
            select(func.count())
            .select_from(TaskDetail)
            .where(TaskDetail.is_active == 1)
        )
        or 0
    )
    if total_tasks == 0:
        project.progress_percent = 0
        return
    completed = (
        db.scalar(
            select(func.count())
            .select_from(ProjectProgress)
            .join(TaskDetail, TaskDetail.task_id == ProjectProgress.task_id)
            .where(
                ProjectProgress.project_id == project.project_id,
                ProjectProgress.status == "已完成",
                TaskDetail.is_active == 1,
            )
        )
        or 0
    )
    project.progress_percent = min(100, max(0, round(100 * completed / total_tasks)))


def sync_current_stage(db: Session, project: ProjectProfile) -> None:
    """按已触达任务自动推算 current_stage_id（取 sort_order 最大；排除阶段 3）。"""
    stage_id = db.scalar(
        select(StageMap.stage_id)
        .select_from(ProjectProgress)
        .join(TaskDetail, TaskDetail.task_id == ProjectProgress.task_id)
        .join(StageMap, StageMap.stage_id == TaskDetail.stage_id)
        .where(
            ProjectProgress.project_id == project.project_id,
            ProjectProgress.status.in_(STAGE_TOUCH_STATUSES),
            TaskDetail.is_active == 1,
            TaskDetail.stage_id.notin_(AUTO_STAGE_EXCLUDE_IDS),
        )
        .order_by(StageMap.sort_order.desc())
        .limit(1)
    )
    project.current_stage_id = stage_id


def sync_project_status(db: Session, project: ProjectProfile) -> None:
    """卡点同步 project_status；current_stage_id 按已触达阶段自动推算。"""
    has_blocker = (
        db.scalar(
            select(func.count())
            .select_from(ProjectProgress)
            .join(TaskDetail, TaskDetail.task_id == ProjectProgress.task_id)
            .where(
                ProjectProgress.project_id == project.project_id,
                ProjectProgress.status == "卡点",
                TaskDetail.is_active == 1,
            )
        )
        or 0
    ) > 0

    if has_blocker:
        project.project_status = "卡点"
    elif project.project_status == "卡点":
        project.project_status = "进行中"

    sync_current_stage(db, project)


def upsert_progress(
    db: Session,
    project_id: int,
    task_id: int,
    body: ProgressUpdate,
    actor: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ProgressOut:
    if body.status not in VALID_STATUSES:
        raise ValueError(f"无效状态: {body.status}")

    project = db.get(ProjectProfile, project_id)
    if not project:
        raise LookupError("企业不存在")

    task = db.get(TaskDetail, task_id)
    if not task:
        raise LookupError("任务不存在")
    if not task.is_active:
        raise ValueError("任务已停用，无法更新进度")

    row = db.execute(
        select(ProjectProgress).where(
            ProjectProgress.project_id == project_id,
            ProjectProgress.task_id == task_id,
        )
    ).scalar_one_or_none()

    before = _progress_snapshot(row) if row else None

    if row is None:
        row = ProjectProgress(project_id=project_id, task_id=task_id)
        db.add(row)

    data = body.model_dump(exclude_unset=True)
    row.status = body.status
    if "assigned_to" in data:
        row.assigned_to = data["assigned_to"]
    if "planned_start" in data:
        row.planned_start = data["planned_start"]
    if "planned_end" in data:
        row.planned_end = data["planned_end"]
    if "started_at" in data:
        row.started_at = data["started_at"]
    if "vendor" in data:
        row.vendor = data["vendor"]

    if body.status == "卡点":
        row.blocker_note = body.blocker_note
    else:
        row.blocker_note = None

    if "completed_at" in data:
        row.completed_at = data["completed_at"]
    elif body.status == "已完成":
        if not row.completed_at:
            row.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    else:
        row.completed_at = None

    db.flush()
    recalculate_progress_percent(db, project)
    sync_project_status(db, project)

    after = _progress_snapshot(row)
    log_progress_update(
        db, actor, project_id, task_id, before=before, after=after,
        ip_address=ip_address, user_agent=user_agent,
    )

    db.commit()
    db.refresh(row)

    return to_progress_out(row, task)
