"""进度写入服务 - Phase C"""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from models import ProjectProfile, ProjectProgress, StageMap, TaskDetail
from schemas import ProgressOut, ProgressUpdate
from services.audit import log_progress_update

VALID_STATUSES = frozenset({"待开始", "进行中", "已完成", "已跳过", "卡点"})
# 已触达：出现这些状态的任务进度即视为该阶段有工作记录（用于推算当前阶段/线性前序）
STAGE_TOUCH_STATUSES = frozenset({"进行中", "已完成", "卡点", "已跳过"})
# 单事项进度权重：待开始=0，进行中/卡点=0.5，已完成/已跳过=1
STATUS_WEIGHT_FULL = frozenset({"已完成", "已跳过"})
STATUS_WEIGHT_HALF = frozenset({"进行中", "卡点"})
# 公用工程及服务类合同签定：可与主链并行，不作为「当前阶段」（stage_id=4）
AUTO_STAGE_EXCLUDE_IDS = frozenset({4})

# 线性主链顺序（跳过并行阶段 3、4）；后阶段有进度时，前阶段整阶段视为已完成
LINEAR_STAGE_ORDER = (1, 2, 5, 6, 7, 8, 9)
LINEAR_STAGES = frozenset(LINEAR_STAGE_ORDER)
# 阶段 5–8 任一已触达时，当前阶段按最大触达前推（不受 1/2/3 空缺钳制）
ADVANCED_LINEAR_UNLOCK = frozenset({5, 6, 7, 8})
# 并行阶段：默认仅按事项权重计入；阶段3在线性到达阶段5及之后时整段视为完成
PARALLEL_STAGES = frozenset({3, 4})
STAGE4_ID = 4
# 线性触达该阶段（或更后）时，阶段3全部事项视为已完成
STAGE3_AUTOCOMPLETE_FROM_LINEAR = 5
# 阶段4：无记录或「已跳过」不计入分母/分子（按项目裁剪清单）
STAGE4_OUT_OF_SCOPE_STATUSES = frozenset({"已跳过"})


def status_progress_weight(status: str) -> float:
    if status in STATUS_WEIGHT_FULL:
        return 1.0
    if status in STATUS_WEIGHT_HALF:
        return 0.5
    return 0.0


def _stage4_in_scope(status: str) -> bool:
    """阶段4事项是否计入分母/分子：有记录且非已跳过。"""
    return status not in STAGE4_OUT_OF_SCOPE_STATUSES


def _weighted_contribution(stage_id: int, status: str) -> float:
    if stage_id == STAGE4_ID and not _stage4_in_scope(status):
        return 0.0
    return status_progress_weight(status)


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


def to_default_progress_out(project_id: int, task: TaskDetail) -> ProgressOut:
    """尚无 project_progress 行时的占位（二级父任务等常未写入）。progress_id=0 表示未落库。"""
    return ProgressOut(
        progress_id=0,
        project_id=project_id,
        task_id=task.task_id,
        task_code=task.task_code,
        task_name=task.task_name,
        stage_id=task.stage_id,
        status="待开始",
        assigned_to=None,
        started_at=None,
        completed_at=None,
        planned_start=None,
        planned_end=None,
        vendor=None,
        blocker_note=None,
        critical_path=task.critical_path,
    )


def list_project_progress(db: Session, project_id: int) -> list[ProgressOut]:
    """
    返回项目全部启用任务的进度视图：有记录用真实行，无记录补「待开始」。
    这样二级父任务（Excel 导入常只写三级叶节点）也会出现在任务进度表中。
    """
    rows = db.execute(
        select(TaskDetail, ProjectProgress)
        .outerjoin(
            ProjectProgress,
            (ProjectProgress.task_id == TaskDetail.task_id)
            & (ProjectProgress.project_id == project_id),
        )
        .where(TaskDetail.is_active == 1)
        .order_by(TaskDetail.sort_order, TaskDetail.task_code)
    ).all()
    out: list[ProgressOut] = []
    for task, pg in rows:
        if pg is None:
            out.append(to_default_progress_out(project_id, task))
        else:
            out.append(to_progress_out(pg, task))
    return out


def recalculate_progress_percent(db: Session, project: ProjectProfile) -> None:
    """
    按任务数加权计算 progress_percent（0-100）。

    规则：
    1. 阶段 0 不计入分母/分子
    2. 线性阶段（1→2→5→6→7→8→9）：若阶段 N 有触达进度，则 N 之前的线性阶段
       全部任务视为已完成（权重 1）；阶段 N 及之后按事项状态权重计入
    3. 并行阶段 4：仅「有记录且非已跳过」的事项计入分母与分子；缺失/已跳过剔除
    4. 并行阶段 3：线性到达阶段 5（或之后）时整段视为已完成；否则按事项权重计入
    5. 单事项权重：待开始=0，进行中/卡点=0.5，已完成/已跳过=1
       （阶段4的已跳过除外：直接剔除，不走权重1）

    「有进度/有记录」（推算当前阶段）= status ∈ STAGE_TOUCH_STATUSES（待开始不算）
    """
    pid = project.project_id

    # 分母：非阶段4用全量启用任务；阶段4按本项目在册且非已跳过裁剪
    base_denominator = (
        db.scalar(
            select(func.count())
            .select_from(TaskDetail)
            .where(
                TaskDetail.is_active == 1,
                TaskDetail.stage_id != 0,
                TaskDetail.stage_id != STAGE4_ID,
            )
        )
        or 0
    )
    stage4_denominator = (
        db.scalar(
            select(func.count())
            .select_from(ProjectProgress)
            .join(TaskDetail, TaskDetail.task_id == ProjectProgress.task_id)
            .where(
                ProjectProgress.project_id == pid,
                TaskDetail.is_active == 1,
                TaskDetail.stage_id == STAGE4_ID,
                ProjectProgress.status.notin_(STAGE4_OUT_OF_SCOPE_STATUSES),
            )
        )
        or 0
    )
    total_denominator = base_denominator + stage4_denominator
    if total_denominator == 0:
        project.progress_percent = 0
        return

    touched_stage_ids = {
        sid
        for (sid,) in db.execute(
            select(TaskDetail.stage_id)
            .join(ProjectProgress, ProjectProgress.task_id == TaskDetail.task_id)
            .where(
                ProjectProgress.project_id == pid,
                TaskDetail.is_active == 1,
                TaskDetail.stage_id != 0,
                ProjectProgress.status.in_(STAGE_TOUCH_STATUSES),
            )
            .distinct()
        ).all()
    }

    furthest_idx = -1
    for i, sid in enumerate(LINEAR_STAGE_ORDER):
        if sid in touched_stage_ids:
            furthest_idx = i
    # 前序线性阶段整阶段自动完成（不含当前最远阶段本身）
    auto_complete_stages = set(LINEAR_STAGE_ORDER[:furthest_idx]) if furthest_idx > 0 else set()
    # 线性到达阶段5及之后：阶段3全部视为完成
    furthest_linear = LINEAR_STAGE_ORDER[furthest_idx] if furthest_idx >= 0 else None
    if furthest_linear is not None and furthest_linear >= STAGE3_AUTOCOMPLETE_FROM_LINEAR:
        auto_complete_stages.add(3)

    auto_completed = 0.0
    if auto_complete_stages:
        auto_completed = float(
            db.scalar(
                select(func.count())
                .select_from(TaskDetail)
                .where(
                    TaskDetail.is_active == 1,
                    TaskDetail.stage_id.in_(auto_complete_stages),
                )
            )
            or 0
        )

    # 非自动完成阶段：按状态权重累计（含阶段4在册非已跳过）
    weight_q = (
        select(TaskDetail.stage_id, ProjectProgress.status)
        .join(TaskDetail, TaskDetail.task_id == ProjectProgress.task_id)
        .where(
            ProjectProgress.project_id == pid,
            TaskDetail.is_active == 1,
            TaskDetail.stage_id != 0,
        )
    )
    if auto_complete_stages:
        weight_q = weight_q.where(TaskDetail.stage_id.notin_(auto_complete_stages))
    weighted_elsewhere = sum(
        _weighted_contribution(stage_id, status)
        for stage_id, status in db.execute(weight_q).all()
    )

    completed_count = auto_completed + weighted_elsewhere
    project.progress_percent = min(100, max(0, round(100 * completed_count / total_denominator)))


def resolve_current_stage_id(
    touched_stage_ids: set[int],
    stage_sort_orders: dict[int, int],
) -> int | None:
    """按已触达阶段推算 current_stage_id（调用方已排除阶段 4）。

    双模式：
    1. 阶段 5–8 任一已触达 → 旧规则：取触达阶段中 sort_order 最大者
       （即使 1/2/3 有空缺也允许前推）
    2. 否则 → 线性前序钳制：不得越过整段未触达的线性阶段；
       阶段 1 未触达 → 0；并行阶段 3 可计入，但不得越过未触达的线性前序
    """
    if not touched_stage_ids:
        return None

    if touched_stage_ids & ADVANCED_LINEAR_UNLOCK:
        return max(touched_stage_ids, key=lambda sid: stage_sort_orders.get(sid, -1))

    gap_idx = next(
        (i for i, sid in enumerate(LINEAR_STAGE_ORDER) if sid not in touched_stage_ids),
        None,
    )
    if gap_idx == 0:
        return 0

    ceiling = None
    if gap_idx is not None:
        ceiling = stage_sort_orders.get(LINEAR_STAGE_ORDER[gap_idx])

    cands: list[tuple[int, int]] = []
    for sid in touched_stage_ids:
        so = stage_sort_orders.get(sid)
        if so is None:
            continue
        if ceiling is None or so < ceiling:
            cands.append((sid, so))
    if cands:
        return max(cands, key=lambda x: x[1])[0]
    if gap_idx and gap_idx > 0:
        return LINEAR_STAGE_ORDER[gap_idx - 1]
    return 0


def refresh_current_stages(db: Session, projects: list[ProjectProfile]) -> bool:
    """按进度批量重算 current_stage_id；有变更返回 True（调用方负责 commit）。

    一次查询拉取全部触达阶段，避免按项目 N+1。
    """
    if not projects:
        return False

    project_ids = [p.project_id for p in projects]
    touched_rows = db.execute(
        select(ProjectProgress.project_id, TaskDetail.stage_id)
        .join(TaskDetail, TaskDetail.task_id == ProjectProgress.task_id)
        .where(
            ProjectProgress.project_id.in_(project_ids),
            ProjectProgress.status.in_(STAGE_TOUCH_STATUSES),
            TaskDetail.is_active == 1,
            TaskDetail.stage_id.notin_(AUTO_STAGE_EXCLUDE_IDS),
        )
        .distinct()
    ).all()
    touched_by_project: dict[int, set[int]] = {}
    for pid, sid in touched_rows:
        touched_by_project.setdefault(pid, set()).add(sid)

    stage_sort_orders = dict(db.execute(select(StageMap.stage_id, StageMap.sort_order)).all())
    changed = False
    for p in projects:
        expected = resolve_current_stage_id(
            touched_by_project.get(p.project_id, set()),
            stage_sort_orders,
        )
        if p.current_stage_id != expected:
            p.current_stage_id = expected
            changed = True
    return changed


def ensure_current_stages(db: Session, projects: list[ProjectProfile]) -> list[ProjectProfile]:
    """读路径：若缓存阶段过期则写回并重新加载（含 current_stage）。"""
    if not projects:
        return projects
    if not refresh_current_stages(db, projects):
        return projects
    ids = [p.project_id for p in projects]
    db.commit()
    return list(
        db.execute(
            select(ProjectProfile)
            .options(joinedload(ProjectProfile.current_stage))
            .where(ProjectProfile.project_id.in_(ids))
        )
        .scalars()
        .unique()
        .all()
    )


def sync_current_stage(db: Session, project: ProjectProfile) -> None:
    """按已触达任务自动推算 current_stage_id（排除阶段 4；见 resolve_current_stage_id）。"""
    refresh_current_stages(db, [project])


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
