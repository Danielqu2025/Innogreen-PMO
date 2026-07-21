"""避坑指南写入服务 - Phase C3"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import PitfallGuide, StageMap, StagePitfallRef
from schemas import PitfallCreate, PitfallOut
from services.audit import log_pitfall_create

VALID_IMPACT_LEVELS = frozenset({"极高", "高", "中", "低"})
VALID_REF_TYPES = frozenset({"常见", "偶尔", "罕见"})


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
    if not stage_ref or not wrong or not right:
        raise ValueError("阶段、错误做法、合规做法不能为空")

    if body.impact_level not in VALID_IMPACT_LEVELS:
        raise ValueError(f"无效影响等级: {body.impact_level}")

    if body.ref_type not in VALID_REF_TYPES:
        raise ValueError(f"无效关联类型: {body.ref_type}")

    stage = db.execute(
        select(StageMap).where(StageMap.stage_name == stage_ref)
    ).scalar_one_or_none()
    if not stage:
        raise ValueError(f"阶段不存在: {stage_ref}")

    pitfall = PitfallGuide(
        stage_ref=stage_ref,
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
