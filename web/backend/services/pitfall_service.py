"""避坑指南写入服务 - Phase C3"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import PitfallGuide, StageMap, StagePitfallRef, TaskDetail
from schemas import PitfallCreate, PitfallOut
from services.audit import log_pitfall_create

VALID_IMPACT_LEVELS = frozenset({"极高", "高", "中", "低"})
VALID_REF_TYPES = frozenset({"常见", "偶尔", "罕见"})


def _task_level(task_code: str | None) -> int:
    """task_code 含 N 个 '.' 即 N+1 级。空/None 视为非法。"""
    if not task_code or "." not in task_code:
        return 0
    return task_code.count(".") + 1


def create_pitfall(
    db: Session,
    body: PitfallCreate,
    actor: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> PitfallOut:
    stage_ref = body.stage_ref.strip()
    wrong = body.wrong_action.strip()
    right = body.right_action.strip()
    task_ref = body.task_ref.strip()
    if not stage_ref or not wrong or not right:
        raise ValueError("阶段、错误做法、合规做法不能为空")
    if not task_ref:
        raise ValueError("关联任务不能为空")

    # task_ref 必为系统已存在的二级或三级任务
    level = _task_level(task_ref)
    if level not in (2, 3):
        raise ValueError(
            f"关联任务须为二级或三级任务编号（如 '3.2' 或 '1.3.1'），收到: {task_ref}"
        )

    if body.impact_level not in VALID_IMPACT_LEVELS:
        raise ValueError(f"无效影响等级: {body.impact_level}")

    if body.ref_type not in VALID_REF_TYPES:
        raise ValueError(f"无效关联类型: {body.ref_type}")

    # 支持 stage_ref 为整数 (stage_id) 或字符串 (stage_name)
    if stage_ref.isdigit():
        stage = db.get(StageMap, int(stage_ref))
    else:
        stage = db.execute(
            select(StageMap).where(StageMap.stage_name == stage_ref)
        ).scalar_one_or_none()
    if not stage:
        raise ValueError(f"阶段不存在: {stage_ref}")

    task = db.execute(
        select(TaskDetail).where(
            TaskDetail.task_code == task_ref,
            TaskDetail.is_active == 1,
        )
    ).scalar_one_or_none()
    if not task:
        raise ValueError(f"关联任务不存在或已停用: {task_ref}")
    if task.stage_id != stage.stage_id:
        raise ValueError(
            f"关联任务 {task_ref} 属于阶段 '{task.stage.stage_name if task.stage else task.stage_id}'，"
            f"与所选阶段不一致"
        )

    pitfall = PitfallGuide(
        stage_ref=stage_ref,
        task_ref=task_ref,
        wrong_action=wrong,
        right_action=right,
        standard_ref=body.standard_ref,
        impact_level=body.impact_level,
        error_index=body.impact_level,
        trigger_condition=body.trigger_condition,
        remediation=body.remediation,
        notes=body.notes,
        source=body.source,
        verified=0,
    )
    db.add(pitfall)
    db.flush()

    db.add(
        StagePitfallRef(
            stage_id=stage.stage_id,
            pitfall_id=pitfall.pitfall_id,
            ref_type=body.ref_type,
        )
    )

    payload = {
        "stage_ref": stage_ref,
        "task_ref": task_ref,
        "wrong_action": wrong,
        "right_action": right,
        "impact_level": body.impact_level,
        "stage_id": stage.stage_id,
    }
    log_pitfall_create(
        db, actor, pitfall.pitfall_id, payload,
        ip_address=ip_address, user_agent=user_agent,
    )
    db.commit()
    db.refresh(pitfall)
    return PitfallOut.model_validate(pitfall)
