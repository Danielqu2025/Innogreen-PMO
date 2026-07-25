from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from database import get_db
from deps import AdminUser, WriteUser, escape_like, get_current_user
from models import (
    PitfallGuide,
    ProjectProgress,
    ProjectProfile,
    StageMap,
    StagePitfallRef,
    TaskDependency,
    TaskDetail,
)
from rate_limit import get_real_ip, limiter
from schemas import (
    AuditLogOut,
    BlockerOut,
    CriticalPathOut,
    DashboardSummary,
    DbImportResultOut,
    ImportSummaryOut,
    JournalCreate,
    JournalOut,
    JournalUpdate,
    PitfallOut,
    PitfallCreate,
    ProgressOut,
    ProgressUpdate,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    StageOut,
    TaskCreate,
    TaskDependencyOut,
    TaskOut,
    TaskUpdate,
)
from services.dashboard_service import build_dashboard_summary
from services.critical_path import build_critical_path, get_project_or_none
from services import journal_service
from services.pitfall_service import create_pitfall
from services.progress_service import (
    ensure_current_stages,
    list_project_progress,
    to_progress_out,
    upsert_progress,
)
from services.project_service import (
    ConflictError,
    create_project,
    sort_projects_for_list,
    update_project,
)
from services import task_service
from services.qcc_service import (
    get_expiring_qualifications,
    is_qcc_available,
    list_company_qualifications,
    lookup_company_by_credit_code,
    lookup_company_by_name,
    qualification_stats,
)

router = APIRouter(prefix="/api/ops", dependencies=[Depends(get_current_user)])

# 上传体积上限（拒绝过大 body，防内存撑爆）
MAX_EXCEL_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MiB
MAX_DB_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MiB
_READ_CHUNK = 1024 * 1024  # 1 MiB


def _client_ip(request: Request) -> str | None:
    return get_real_ip(request)


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


async def _read_upload_limited(
    request: Request,
    file: UploadFile,
    max_bytes: int,
    *,
    kind: str,
) -> bytes:
    """读取上传文件并强制上限。优先看 Content-Length，再按块读并计数。"""
    cl = request.headers.get("content-length")
    if cl is not None:
        try:
            if int(cl) > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail={
                        "error": True,
                        "code": "ERR_PAYLOAD_TOO_LARGE",
                        "message": (
                            f"{kind} 上传过大（Content-Length {cl} 字节，"
                            f"上限 {max_bytes // (1024 * 1024)} MB）"
                        ),
                    },
                )
        except ValueError:
            pass

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_READ_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail={
                    "error": True,
                    "code": "ERR_PAYLOAD_TOO_LARGE",
                    "message": (
                        f"{kind} 上传过大（超过上限 "
                        f"{max_bytes // (1024 * 1024)} MB）"
                    ),
                },
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _project_out(p: ProjectProfile) -> ProjectOut:
    return ProjectOut(
        project_id=p.project_id,
        project_code=p.project_code,
        company_name=p.company_name,
        short_name=p.short_name,
        full_name=p.full_name,
        business_type=p.business_type,
        building=p.building,
        current_stage_id=p.current_stage_id,
        current_stage_name=p.current_stage.stage_name if p.current_stage else None,
        project_status=p.project_status,
        progress_percent=p.progress_percent,
        notes=p.notes,
    )


@router.get("/stages", response_model=list[StageOut])
def list_stages(db: Session = Depends(get_db)) -> list[StageOut]:
    stages = db.execute(select(StageMap).order_by(StageMap.sort_order)).scalars().all()
    counts = dict(
        db.execute(
            select(TaskDetail.stage_id, func.count())
            .where(TaskDetail.is_active == 1)
            .group_by(TaskDetail.stage_id)
        ).all()
    )
    return [
        StageOut(
            stage_id=s.stage_id,
            stage_name=s.stage_name,
            primary_owner=s.primary_owner,
            critical_path=s.critical_path,
            default_days=s.default_days,
            description=s.description,
            sort_order=s.sort_order,
            task_count=int(counts.get(s.stage_id, 0)),
        )
        for s in stages
    ]


@router.get("/stages/{stage_id}", response_model=StageOut)
def get_stage(stage_id: int, db: Session = Depends(get_db)) -> StageOut:
    s = db.get(StageMap, stage_id)
    if not s:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "阶段不存在"},
        )
    count = db.execute(
        select(func.count())
        .select_from(TaskDetail)
        .where(TaskDetail.stage_id == stage_id, TaskDetail.is_active == 1)
    ).scalar_one()
    return StageOut(
        stage_id=s.stage_id,
        stage_name=s.stage_name,
        primary_owner=s.primary_owner,
        critical_path=s.critical_path,
        default_days=s.default_days,
        description=s.description,
        sort_order=s.sort_order,
        task_count=int(count),
    )


@router.get("/stages/{stage_id}/tasks", response_model=list[TaskOut])
def list_stage_tasks(
    stage_id: int,
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
) -> list[TaskOut]:
    if not db.get(StageMap, stage_id):
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "阶段不存在"},
        )
    q = select(TaskDetail).where(TaskDetail.stage_id == stage_id)
    if not include_inactive:
        q = q.where(TaskDetail.is_active == 1)
    tasks = db.execute(q.order_by(TaskDetail.sort_order)).scalars().all()
    return [TaskOut.model_validate(t) for t in tasks]


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(
    stage_id: int | None = None,
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
) -> list[TaskOut]:
    q = select(TaskDetail).order_by(TaskDetail.sort_order)
    if stage_id is not None:
        q = q.where(TaskDetail.stage_id == stage_id)
    if not include_inactive:
        q = q.where(TaskDetail.is_active == 1)
    return [TaskOut.model_validate(t) for t in db.execute(q).scalars().all()]


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)) -> TaskOut:
    t = db.get(TaskDetail, task_id)
    if not t:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "任务不存在"},
        )
    return TaskOut.model_validate(t)


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task_endpoint(
    body: TaskCreate,
    request: Request,
    user: AdminUser,
    db: Session = Depends(get_db),
) -> TaskOut:
    try:
        return task_service.create_task(
            db,
            body,
            user.username,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except task_service.ConflictError as e:
        raise HTTPException(
            409,
            detail={"error": True, "code": "ERR_CONFLICT", "message": str(e)},
        ) from e
    except ValueError as e:
        raise HTTPException(
            400,
            detail={"error": True, "code": "ERR_VALIDATION", "message": str(e)},
        ) from e


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task_endpoint(
    task_id: int,
    body: TaskUpdate,
    request: Request,
    user: AdminUser,
    db: Session = Depends(get_db),
) -> TaskOut:
    try:
        return task_service.update_task(
            db,
            task_id,
            body,
            user.username,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except LookupError as e:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": str(e)},
        ) from e
    except task_service.ConflictError as e:
        raise HTTPException(
            409,
            detail={"error": True, "code": "ERR_CONFLICT", "message": str(e)},
        ) from e
    except ValueError as e:
        raise HTTPException(
            400,
            detail={"error": True, "code": "ERR_VALIDATION", "message": str(e)},
        ) from e


@router.post("/tasks/{task_id}/deactivate", response_model=TaskOut)
def deactivate_task(
    task_id: int,
    request: Request,
    user: AdminUser,
    db: Session = Depends(get_db),
) -> TaskOut:
    try:
        return task_service.set_task_active(
            db,
            task_id,
            False,
            user.username,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except LookupError as e:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": str(e)},
        ) from e


@router.post("/tasks/{task_id}/activate", response_model=TaskOut)
def activate_task(
    task_id: int,
    request: Request,
    user: AdminUser,
    db: Session = Depends(get_db),
) -> TaskOut:
    try:
        return task_service.set_task_active(
            db,
            task_id,
            True,
            user.username,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except LookupError as e:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": str(e)},
        ) from e


@router.get("/tasks/{task_id}/dependencies", response_model=list[TaskDependencyOut])
def task_dependencies(task_id: int, db: Session = Depends(get_db)) -> list[TaskDependencyOut]:
    if not db.get(TaskDetail, task_id):
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "任务不存在"},
        )
    deps = (
        db.execute(
            select(TaskDependency).where(
                (TaskDependency.task_id == task_id) | (TaskDependency.depends_on == task_id)
            )
        )
        .scalars()
        .all()
    )
    task_map = {t.task_id: t for t in db.execute(select(TaskDetail)).scalars().all()}
    out: list[TaskDependencyOut] = []
    for d in deps:
        a = task_map.get(d.task_id)
        b = task_map.get(d.depends_on)
        out.append(
            TaskDependencyOut(
                task_id=d.task_id,
                depends_on=d.depends_on,
                dependency_type=d.dependency_type,
                task_code=a.task_code if a else None,
                task_name=a.task_name if a else None,
                depends_on_code=b.task_code if b else None,
                depends_on_name=b.task_name if b else None,
            )
        )
    return out


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(
    status: str | None = None,
    stage_id: int | None = None,
    building: str | None = None,
    q: str | None = None,
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
) -> list[ProjectOut]:
    query = (
        select(ProjectProfile)
        .options(joinedload(ProjectProfile.current_stage))
    )
    if not include_inactive:
        query = query.where(ProjectProfile.is_active == 1)
    if status:
        query = query.where(ProjectProfile.project_status == status)
    if building:
        query = query.where(ProjectProfile.building == building)
    if q:
        like = f"%{escape_like(q)}%"
        query = query.where(
            (ProjectProfile.project_code.like(like, escape="\\"))
            | (ProjectProfile.company_name.like(like, escape="\\"))
            | (ProjectProfile.short_name.like(like, escape="\\"))
            | (ProjectProfile.full_name.like(like, escape="\\"))
        )
    # 先按进度刷新 current_stage_id，再按 stage_id 过滤（避免缓存过期漏筛/错筛）
    projects = ensure_current_stages(
        db, list(db.execute(query).scalars().unique().all())
    )
    if stage_id is not None:
        projects = [p for p in projects if p.current_stage_id == stage_id]
    projects = sort_projects_for_list(projects)
    return [_project_out(p) for p in projects]


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project_endpoint(
    body: ProjectCreate,
    request: Request,
    user: WriteUser,
    db: Session = Depends(get_db),
) -> ProjectOut:
    try:
        return create_project(
            db,
            body,
            user.username,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except ConflictError as e:
        raise HTTPException(
            409,
            detail={"error": True, "code": "ERR_CONFLICT", "message": str(e)},
        ) from e
    except ValueError as e:
        raise HTTPException(
            400,
            detail={"error": True, "code": "ERR_BAD_REQUEST", "message": str(e)},
        ) from e


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)) -> ProjectOut:
    p = get_project_or_none(db, project_id)
    if not p:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "企业不存在"},
        )
    refreshed = ensure_current_stages(db, [p])
    return _project_out(refreshed[0])


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project_endpoint(
    project_id: int,
    body: ProjectUpdate,
    request: Request,
    user: WriteUser,
    db: Session = Depends(get_db),
) -> ProjectOut:
    try:
        return update_project(
            db,
            project_id,
            body,
            user.username,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except LookupError as e:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": str(e)},
        ) from e
    except ConflictError as e:
        raise HTTPException(
            409,
            detail={"error": True, "code": "ERR_CONFLICT", "message": str(e)},
        ) from e
    except ValueError as e:
        raise HTTPException(
            400,
            detail={"error": True, "code": "ERR_BAD_REQUEST", "message": str(e)},
        ) from e


@router.post("/projects/{project_id}/deactivate", response_model=ProjectOut)
def deactivate_project(
    project_id: int,
    request: Request,
    user: AdminUser,
    db: Session = Depends(get_db),
) -> ProjectOut:
    """软删除项目（管理员专用）"""
    p = db.get(ProjectProfile, project_id)
    if not p:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "企业不存在"},
        )
    if p.is_active == 0:
        raise HTTPException(
            400,
            detail={"error": True, "code": "ERR_BAD_REQUEST", "message": "项目已停用"},
        )
    p.is_active = 0
    from services.audit import log_action
    log_action(
        db,
        user.username,
        "DELETE",
        "projects",
        project_id,
        payload={"project_code": p.project_code, "company_name": p.company_name},
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    db.commit()
    db.refresh(p)
    return _project_out(p)


@router.post("/projects/{project_id}/activate", response_model=ProjectOut)
def activate_project(
    project_id: int,
    request: Request,
    user: AdminUser,
    db: Session = Depends(get_db),
) -> ProjectOut:
    """恢复已停用项目（管理员专用）"""
    p = db.get(ProjectProfile, project_id)
    if not p:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "企业不存在"},
        )
    if p.is_active == 1:
        raise HTTPException(
            400,
            detail={"error": True, "code": "ERR_BAD_REQUEST", "message": "项目已是活跃状态"},
        )
    p.is_active = 1
    from services.audit import log_action
    log_action(
        db,
        user.username,
        "RESTORE",
        "projects",
        project_id,
        payload={"project_code": p.project_code, "company_name": p.company_name},
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    db.commit()
    db.refresh(p)
    return _project_out(p)


@router.get("/projects/{project_id}/progress", response_model=list[ProgressOut])
def project_progress(project_id: int, db: Session = Depends(get_db)) -> list[ProgressOut]:
    if not db.get(ProjectProfile, project_id):
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "企业不存在"},
        )
    return list_project_progress(db, project_id)


@router.get("/projects/{project_id}/journal", response_model=list[JournalOut])
def list_project_journal(
    project_id: int,
    task_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[JournalOut]:
    try:
        return journal_service.list_journals(
            db, project_id, task_id=task_id, limit=limit
        )
    except LookupError as e:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": str(e)},
        ) from e


@router.get(
    "/projects/{project_id}/tasks/{task_id}/journal",
    response_model=list[JournalOut],
)
def list_task_journal(
    project_id: int,
    task_id: int,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[JournalOut]:
    try:
        return journal_service.list_journals(
            db, project_id, task_id=task_id, limit=limit
        )
    except LookupError as e:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": str(e)},
        ) from e


@router.post(
    "/projects/{project_id}/tasks/{task_id}/journal",
    response_model=JournalOut,
    status_code=201,
)
def create_task_journal(
    project_id: int,
    task_id: int,
    body: JournalCreate,
    request: Request,
    user: WriteUser,
    db: Session = Depends(get_db),
) -> JournalOut:
    try:
        return journal_service.create_journal(
            db,
            project_id,
            task_id,
            body,
            user.username,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except LookupError as e:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": str(e)},
        ) from e
    except journal_service.ConflictError as e:
        raise HTTPException(
            409,
            detail={"error": True, "code": "ERR_CONFLICT", "message": str(e)},
        ) from e
    except ValueError as e:
        raise HTTPException(
            400,
            detail={"error": True, "code": "ERR_VALIDATION", "message": str(e)},
        ) from e


@router.patch(
    "/projects/{project_id}/tasks/{task_id}/journal/{journal_id}",
    response_model=JournalOut,
)
def update_task_journal(
    project_id: int,
    task_id: int,
    journal_id: int,
    body: JournalUpdate,
    request: Request,
    user: WriteUser,
    db: Session = Depends(get_db),
) -> JournalOut:
    try:
        return journal_service.update_journal(
            db,
            project_id,
            task_id,
            journal_id,
            body,
            user.username,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except LookupError as e:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": str(e)},
        ) from e
    except journal_service.ConflictError as e:
        raise HTTPException(
            409,
            detail={"error": True, "code": "ERR_CONFLICT", "message": str(e)},
        ) from e
    except ValueError as e:
        raise HTTPException(
            400,
            detail={"error": True, "code": "ERR_VALIDATION", "message": str(e)},
        ) from e


@router.delete(
    "/projects/{project_id}/tasks/{task_id}/journal/{journal_id}",
    status_code=204,
)
def delete_task_journal(
    project_id: int,
    task_id: int,
    journal_id: int,
    request: Request,
    user: WriteUser,
    db: Session = Depends(get_db),
) -> None:
    try:
        journal_service.delete_journal(
            db,
            project_id,
            task_id,
            journal_id,
            user.username,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except LookupError as e:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": str(e)},
        ) from e


@router.get("/projects/{project_id}/critical-path", response_model=CriticalPathOut)
def project_critical_path(project_id: int, db: Session = Depends(get_db)) -> CriticalPathOut:
    p = get_project_or_none(db, project_id)
    if not p:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "企业不存在"},
        )
    return build_critical_path(db, p)


@router.put(
    "/projects/{project_id}/tasks/{task_id}",
    response_model=ProgressOut,
)
def update_project_task_progress(
    project_id: int,
    task_id: int,
    body: ProgressUpdate,
    request: Request,
    user: WriteUser,
    db: Session = Depends(get_db),
) -> ProgressOut:
    try:
        return upsert_progress(
            db,
            project_id,
            task_id,
            body,
            user.username,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except LookupError as e:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": str(e)},
        ) from e
    except ValueError as e:
        raise HTTPException(
            400,
            detail={"error": True, "code": "ERR_BAD_REQUEST", "message": str(e)},
        ) from e


@router.get("/progress/blockers", response_model=list[BlockerOut])
def list_blockers(db: Session = Depends(get_db)) -> list[BlockerOut]:
    rows = db.execute(
        select(ProjectProgress, ProjectProfile, TaskDetail)
        .join(ProjectProfile, ProjectProfile.project_id == ProjectProgress.project_id)
        .join(TaskDetail, TaskDetail.task_id == ProjectProgress.task_id)
        .where(ProjectProgress.status == "卡点")
        .order_by(ProjectProfile.project_id)
    ).all()
    return [
        BlockerOut(
            project_id=pp.project_id,
            project_code=pp.project_code,
            project=pp.project_code,
            task_id=td.task_id,
            task_code=td.task_code,
            task=td.task_name,
            note=pg.blocker_note,
            project_status=pp.project_status,
        )
        for pg, pp, td in rows
    ]


@router.get("/pitfalls", response_model=list[PitfallOut])
def list_pitfalls(
    stage: str | None = None,
    impact: str | None = None,
    q: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[PitfallOut]:
    query = select(PitfallGuide)
    if stage:
        query = query.where(
            PitfallGuide.stage_ref.like(f"%{escape_like(stage)}%", escape="\\")
        )
    if impact:
        query = query.where(PitfallGuide.impact_level == impact)
    if q:
        like = f"%{escape_like(q)}%"
        query = query.where(
            (PitfallGuide.wrong_action.like(like, escape="\\"))
            | (PitfallGuide.right_action.like(like, escape="\\"))
        )
    return [PitfallOut.model_validate(p) for p in db.execute(query).scalars().all()]


@router.post("/pitfalls", response_model=PitfallOut, status_code=201)
def create_pitfall_endpoint(
    body: PitfallCreate,
    request: Request,
    user: WriteUser,
    db: Session = Depends(get_db),
) -> PitfallOut:
    try:
        return create_pitfall(
            db,
            body,
            user.username,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except ValueError as e:
        raise HTTPException(
            400,
            detail={"error": True, "code": "ERR_BAD_REQUEST", "message": str(e)},
        ) from e


@router.get("/pitfalls/{pitfall_id}", response_model=PitfallOut)
def get_pitfall(pitfall_id: int, db: Session = Depends(get_db)) -> PitfallOut:
    p = db.get(PitfallGuide, pitfall_id)
    if not p:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "避坑不存在"},
        )
    return PitfallOut.model_validate(p)


@router.get("/stages/{stage_id}/pitfalls", response_model=list[PitfallOut])
def stage_pitfalls(stage_id: int, db: Session = Depends(get_db)) -> list[PitfallOut]:
    if not db.get(StageMap, stage_id):
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "阶段不存在"},
        )
    rows = (
        db.execute(
            select(PitfallGuide)
            .join(StagePitfallRef, StagePitfallRef.pitfall_id == PitfallGuide.pitfall_id)
            .where(StagePitfallRef.stage_id == stage_id)
        )
        .scalars()
        .all()
    )
    return [PitfallOut.model_validate(p) for p in rows]


@router.get("/qcc/status")
def qcc_status() -> dict:
    """查询 qcc 数据库连接状态。"""
    available = is_qcc_available()
    return {"available": available}


@router.get("/qcc/companies/lookup")
def qcc_company_lookup(
    credit_code: str | None = Query(None),
    name: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    """
    按统一社会信用代码或企业名称查询 qcc 企业工商信息。
    credit_code 和 name 二选一，优先 credit_code。
    """
    if not is_qcc_available():
        raise HTTPException(
            503,
            detail={
                "error": True,
                "code": "ERR_QCC_UNAVAILABLE",
                "message": "qcc 数据库未配置或文件不存在",
            },
        )

    if not credit_code and not name:
        raise HTTPException(
            400,
            detail={
                "error": True,
                "code": "ERR_MISSING_PARAM",
                "message": "需提供 credit_code 或 name 参数",
            },
        )

    company = None
    if credit_code:
        company = lookup_company_by_credit_code(db, credit_code)
    if not company and name:
        company = lookup_company_by_name(db, name)

    if not company:
        return {"found": False, "company": None, "qualifications": [], "stats": None}

    qcc_company_id = company["id"]
    quals = list_company_qualifications(db, qcc_company_id)
    stats = qualification_stats(db, qcc_company_id)

    return {
        "found": True,
        "company": company,
        "qualifications": quals,
        "stats": stats,
    }


@router.get("/qcc/companies/expiring")
def qcc_expiring_qualifications(
    days: int = Query(30, ge=1, le=180),
    db: Session = Depends(get_db),
) -> list[dict]:
    """
    列出 qcc 中即将到期（默认30天内）的资质证照。
    用于全局到期预警。
    """
    if not is_qcc_available():
        raise HTTPException(
            503,
            detail={
                "error": True,
                "code": "ERR_QCC_UNAVAILABLE",
                "message": "qcc 数据库未配置或文件不存在",
            },
        )
    return get_expiring_qualifications(db, days)


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummary:
    return build_dashboard_summary(db)


@router.get("/export/excel")
def export_excel(
    user: WriteUser,
    db: Session = Depends(get_db),
    sheets: str | None = Query(
        None,
        description="逗号分隔：stages,tasks,projects,progress,pitfalls（或中文 sheet 名）；缺省全部",
    ),
):
    """导出多 sheet Excel。管理员与操作员可用；可用 sheets 筛选。"""
    from datetime import datetime

    from fastapi.responses import Response

    from services.export_service import build_export_workbook, parse_export_sheets

    try:
        keys = parse_export_sheets(sheets)
    except ValueError as e:
        raise HTTPException(
            400,
            detail={"error": True, "code": "ERR_BAD_REQUEST", "message": str(e)},
        ) from e

    data = build_export_workbook(db, sheets=keys)
    filename = f"innogreen_pmo_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/db")
def export_db(user: AdminUser):
    """导出当前 SQLite 库事务一致快照（.db）。仅管理员。"""
    from datetime import datetime

    from fastapi.responses import Response

    from config import get_settings
    from services.db_transfer import snapshot_db_bytes

    try:
        data = snapshot_db_bytes(get_settings().db_path)
    except FileNotFoundError as e:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": str(e)},
        ) from e
    filename = f"innogreen_pmo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    return Response(
        content=data,
        media_type="application/x-sqlite3",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/import/template.xlsx")
def import_template(user: WriteUser):
    """下载 Excel 导入模板（说明字段表 + 企业档案/任务进度示例）。管理员与操作员可用。"""
    from fastapi.responses import Response

    from services.export_service import build_import_template

    data = build_import_template()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="innogreen_pmo_import_template.xlsx"'
        },
    )


@router.post("/import/excel", response_model=ImportSummaryOut)
async def import_excel(
    request: Request,
    user: WriteUser,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    dry_run: bool = Query(True, description="试跑不写库；false 时真正写入"),
) -> ImportSummaryOut:
    """导入企业档案 + 任务进度。管理员与操作员可用；不修改阶段/任务目录。"""
    from services.import_service import import_projects_progress_xlsx

    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(
            400,
            detail={
                "error": True,
                "code": "ERR_BAD_REQUEST",
                "message": "请上传 .xlsx Excel 文件",
            },
        )
    raw = await _read_upload_limited(
        request, file, MAX_EXCEL_UPLOAD_BYTES, kind="Excel"
    )
    if not raw:
        raise HTTPException(
            400,
            detail={"error": True, "code": "ERR_BAD_REQUEST", "message": "文件为空"},
        )

    summary = import_projects_progress_xlsx(
        db,
        raw,
        actor=user.username,
        dry_run=dry_run,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    if summary.errors:
        raise HTTPException(
            400,
            detail={
                "error": True,
                "code": "ERR_IMPORT",
                "message": summary.errors[0],
                "summary": summary.to_dict(),
            },
        )
    return ImportSummaryOut(**summary.to_dict())


@router.post("/import/db", response_model=DbImportResultOut)
@limiter.limit("5/hour")  # 替换库是毁灭性操作，限速兜底（即使管理员 Cookie 泄漏也不能滥用）
async def import_db(
    request: Request,
    response: Response,
    user: AdminUser,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    confirm: bool = Query(
        False,
        description="必须为 true：确认将用上传的 .db 全量替换当前库",
    ),
    migrate: bool = Query(
        False,
        description="智能迁移模式：提取数据而非替换文件（推荐开启）",
    ),
) -> DbImportResultOut:
    """导入 SQLite 数据库。

    - migrate=False（默认）：直接替换数据库文件（危险）
    - migrate=True（推荐）：智能迁移数据，处理 schema 差异
    """
    from config import get_settings
    from services.audit import log_action
    from services.db_transfer import migrate_db_data, replace_live_db, dispose_engine

    if not confirm:
        raise HTTPException(
            400,
            detail={
                "error": True,
                "code": "ERR_CONFIRM_REQUIRED",
                "message": "全量替换数据库需确认：请传 confirm=true",
            },
        )
    name = (file.filename or "").lower()
    if not name.endswith(".db"):
        raise HTTPException(
            400,
            detail={
                "error": True,
                "code": "ERR_BAD_REQUEST",
                "message": "请上传 .db SQLite 文件",
            },
        )
    raw = await _read_upload_limited(
        request, file, MAX_DB_UPLOAD_BYTES, kind="数据库"
    )
    if not raw:
        raise HTTPException(
            400,
            detail={"error": True, "code": "ERR_BAD_REQUEST", "message": "文件为空"},
        )

    if migrate:
        # 智能迁移模式：提取数据写入目标数据库
        log_action(
            db,
            user.username,
            "MIGRATE",
            "database",
            None,
            payload={"bytes": len(raw), "filename": file.filename, "mode": "smart_migrate"},
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
        db.commit()
        db.close()
        dispose_engine()

        try:
            stats = migrate_db_data(raw, get_settings().db_path)
        except Exception as e:
            raise HTTPException(
                400,
                detail={"error": True, "code": "ERR_MIGRATE", "message": f"迁移失败: {e}"},
            ) from e

        return DbImportResultOut(
            ok=True,
            backup_path=stats["backup_path"],
            message=f"智能迁移完成：迁移 {stats['rows_migrated']} 条，更新 {stats['rows_updated']} 条，跳过 {stats['rows_skipped']} 条。先前库已自动备份。",
        )
    else:
        # 传统模式：直接替换文件
        log_action(
            db,
            user.username,
            "IMPORT",
            "database",
            None,
            payload={"bytes": len(raw), "filename": file.filename, "mode": "replace"},
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
        db.commit()
        db.close()

        try:
            backup_path = replace_live_db(get_settings().db_path, raw)
        except ValueError as e:
            raise HTTPException(
                400,
                detail={"error": True, "code": "ERR_IMPORT", "message": str(e)},
            ) from e
        except FileNotFoundError as e:
            raise HTTPException(
                404,
                detail={"error": True, "code": "ERR_NOT_FOUND", "message": str(e)},
            ) from e

        return DbImportResultOut(
            ok=True,
            backup_path=f"backups/{backup_path.name}",
            message="已用上传的数据库替换当前库；先前库已自动备份。如页面异常请刷新或重新登录。",
        )


@router.get("/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
    resource: str | None = Query(None),
    actor: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[AuditLogOut]:
    """查询审计日志（仅管理员可用）"""
    from models import AuditLog as AuditLogModel

    query = select(AuditLogModel)
    if action:
        query = query.where(AuditLogModel.action == action)
    if resource:
        query = query.where(AuditLogModel.resource == resource)
    if actor:
        query = query.where(AuditLogModel.actor == actor)

    query = query.order_by(AuditLogModel.created_at.desc()).offset(offset).limit(limit)
    logs = db.execute(query).scalars().all()
    return [AuditLogOut.model_validate(log) for log in logs]


tenant_router = APIRouter(prefix="/api/tenant")

@tenant_router.get("/me/project")
def tenant_placeholder() -> dict:
    raise HTTPException(
        501,
        detail={
            "error": True,
            "code": "ERR_NOT_IMPLEMENTED",
            "message": "企业端将在 v1.4 开放",
        },
    )
