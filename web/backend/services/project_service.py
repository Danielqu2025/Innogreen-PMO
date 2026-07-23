"""企业档案写入服务 - Phase C"""
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from models import ProjectProfile, StageMap
from schemas import ProjectCreate, ProjectOut, ProjectUpdate
from services.audit import log_project_create, log_project_update

VALID_PROJECT_STATUSES = frozenset({"未开始", "进行中", "卡点", "已完成", "已退园"})

# 企业列表：当前阶段从后往前（阶段 4 插在 5 与 3 之间）；未知/空阶段靠后
_LIST_STAGE_ORDER = (9, 8, 7, 6, 5, 4, 3, 2, 1, 0)
_STAGE_RANK = {sid: i for i, sid in enumerate(_LIST_STAGE_ORDER)}
# 支持 A13 / B5 / ENT-01 / ENT-A01
_CODE_RE = re.compile(r"^(?:ENT-)?([A-Za-z]*)(\d*)(.*)$", re.IGNORECASE)


class ConflictError(Exception):
    pass


def project_code_sort_key(project_code: str) -> tuple:
    """同阶段内：字母 A 先于 B；去掉 ENT- 与前缀字母后按数字升序。"""
    code = (project_code or "").strip()
    m = _CODE_RE.match(code)
    if not m:
        return ("~", 10**9, code.upper())
    letter = (m.group(1) or "").upper()
    digits = m.group(2) or ""
    num = int(digits) if digits else 0
    return (letter, num, code.upper())


def project_list_sort_key(project: ProjectProfile) -> tuple:
    sid = project.current_stage_id
    if sid is None:
        stage_rank = len(_LIST_STAGE_ORDER) + 1000
    else:
        stage_rank = _STAGE_RANK.get(sid, len(_LIST_STAGE_ORDER) + int(sid))
    letter, num, code = project_code_sort_key(project.project_code)
    return (stage_rank, letter, num, code, project.project_id)


def sort_projects_for_list(projects: list[ProjectProfile]) -> list[ProjectProfile]:
    return sorted(projects, key=project_list_sort_key)


def _project_snapshot(project: ProjectProfile) -> dict:
    return {
        "project_code": project.project_code,
        "company_name": project.company_name,
        "short_name": project.short_name,
        "full_name": project.full_name,
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
        full_name=project.full_name,
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
        full_name=(body.full_name.strip() if body.full_name else None),
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

    if "project_code" in updates:
        code = (updates["project_code"] or "").strip()
        if not code:
            raise ValueError("企业编号不能为空")
        updates["project_code"] = code
        if code != project.project_code:
            clash = db.execute(
                select(ProjectProfile).where(
                    ProjectProfile.project_code == code,
                    ProjectProfile.project_id != project_id,
                )
            ).scalar_one_or_none()
            if clash:
                raise ConflictError(f"企业编号已存在: {code}")

    if "full_name" in updates and updates["full_name"] is not None:
        updates["full_name"] = updates["full_name"].strip() or None
    if "short_name" in updates and updates["short_name"] is not None:
        updates["short_name"] = updates["short_name"].strip() or None

    if "project_status" in updates and updates["project_status"] not in VALID_PROJECT_STATUSES:
        raise ValueError(f"无效项目状态: {updates['project_status']}")

    if "current_stage_id" in updates and updates["current_stage_id"] is not None:
        if not db.get(StageMap, updates["current_stage_id"]):
            raise ValueError("阶段不存在")

    before = _project_snapshot(project)
    for field, value in updates.items():
        setattr(project, field, value)

    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise ConflictError("企业编号已存在") from e

    after = _project_snapshot(project)
    log_project_update(
        db, actor, project_id, before, after,
        ip_address=ip_address, user_agent=user_agent,
    )
    db.commit()

    loaded = _load_project(db, project_id)
    assert loaded is not None
    return _to_project_out(loaded)
