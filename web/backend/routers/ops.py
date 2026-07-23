from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from database import get_db
from deps import AdminUser, WriteUser, get_current_user
from models import (
    PitfallGuide,
    ProjectProgress,
    ProjectProfile,
    StageMap,
    StagePitfallRef,
    TaskDependency,
    TaskDetail,
)
from schemas import (
    BlockerOut,
    CriticalPathOut,
    DashboardSummary,
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

router = APIRouter(prefix="/api/ops", dependencies=[Depends(get_current_user)])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


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
    db: Session = Depends(get_db),
) -> list[ProjectOut]:
    query = (
        select(ProjectProfile)
        .options(joinedload(ProjectProfile.current_stage))
    )
    if status:
        query = query.where(ProjectProfile.project_status == status)
    if building:
        query = query.where(ProjectProfile.building == building)
    if q:
        like = f"%{q}%"
        query = query.where(
            (ProjectProfile.project_code.like(like))
            | (ProjectProfile.company_name.like(like))
            | (ProjectProfile.short_name.like(like))
            | (ProjectProfile.full_name.like(like))
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
        query = query.where(PitfallGuide.stage_ref.like(f"%{stage}%"))
    if impact:
        query = query.where(PitfallGuide.impact_level == impact)
    if q:
        like = f"%{q}%"
        query = query.where(
            (PitfallGuide.wrong_action.like(like)) | (PitfallGuide.right_action.like(like))
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


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummary:
    return build_dashboard_summary(db)


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
