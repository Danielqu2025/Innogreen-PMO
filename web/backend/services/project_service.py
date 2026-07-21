"""企业档案写入服务 - Phase C"""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from models import ProjectProfile, StageMap
from schemas import ProjectCreate, ProjectOut, ProjectUpdate
from services.audit import log_project_create, log_project_update

VALID_PROJECT_STATUSES = frozenset({"未开始", "进行中", "卡点", "已完成", "已退园"})


class ConflictError(Exception):
    pass


def _project_snapshot(project: ProjectProfile) -> dict:
    return {
        "project_code": project.project_code,
        "company_name": project.company_name,
        "short_name": project.short_name,
        "business_type": project.business_type,
        "building": project.building,
        "current_stage_id": project.current_stage_id,
        "project_status": project.project_status,
        "progress_percent": project.progress_percent,
        "notes": project.notes,
    }


def _load_project(db: Session, project_id: int) -> ProjectProfile | None:
    return db.execute(
        select(ProjectProfile)
        .options(joinedload(ProjectProfile.current_stage))
        .where(ProjectProfile.project_id == project_id)
    ).scalar_one_or_none()


def _to_project_out(project: ProjectProfile) -> ProjectOut:
    return ProjectOut(
        project_id=project.project_id,
        project_code=project.project_code,
        company_name=project.company_name,
        short_name=project.short_name,
        business_type=project.business_type,
        building=project.building,
        current_stage_id=project.current_stage_id,
        current_stage_name=project.current_stage.stage_name if project.current_stage else None,
        project_status=project.project_status,
        progress_percent=project.progress_percent,
        notes=project.notes,
    )


def create_project(
    db: Session,
    body: ProjectCreate,
    actor: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ProjectOut:
    code = body.project_code.strip()
    name = body.company_name.strip()
    if not code or not name:
        raise ValueError("编号与企业名称不能为空")

    existing = db.execute(
        select(ProjectProfile).where(
            (ProjectProfile.project_code == code) | (ProjectProfile.company_name == name)
        )
    ).scalar_one_or_none()
    if existing:
        if existing.project_code == code:
            raise ConflictError(f"企业编号已存在: {code}")
        raise ConflictError(f"企业名称已存在: {name}")

    project = ProjectProfile(
        project_code=code,
        company_name=name,
        short_name=(body.short_name or code).strip(),
        business_type=body.business_type,
        building=body.building,
        project_status="未开始",
        progress_percent=0,
        notes=body.notes,
    )
    db.add(project)
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise ConflictError("企业编号或名称已存在") from e

    log_project_create(
        db, actor, project.project_id, _project_snapshot(project),
        ip_address=ip_address, user_agent=user_agent,
    )
    db.commit()

    loaded = _load_project(db, project.project_id)
    assert loaded is not None
    return _to_project_out(loaded)


def update_project(
    db: Session,
    project_id: int,
    body: ProjectUpdate,
    actor: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ProjectOut:
    project = _load_project(db, project_id)
    if not project:
        raise LookupError("企业不存在")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("未提供更新字段")

    if "project_status" in updates and updates["project_status"] not in VALID_PROJECT_STATUSES:
        raise ValueError(f"无效项目状态: {updates['project_status']}")

    if "current_stage_id" in updates and updates["current_stage_id"] is not None:
        if not db.get(StageMap, updates["current_stage_id"]):
            raise ValueError("阶段不存在")

    before = _project_snapshot(project)
    for field, value in updates.items():
        setattr(project, field, value)

    db.flush()
    after = _project_snapshot(project)
    log_project_update(
        db, actor, project_id, before, after,
        ip_address=ip_address, user_agent=user_agent,
    )
    db.commit()

    loaded = _load_project(db, project_id)
    assert loaded is not None
    return _to_project_out(loaded)
