from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from database import get_db
from deps import require_token
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
    PitfallOut,
    ProgressOut,
    ProjectOut,
    StageOut,
    TaskDependencyOut,
    TaskOut,
    WriteStubIn,
)
from services.critical_path import build_critical_path, get_project_or_none

router = APIRouter(prefix="/api/ops", dependencies=[Depends(require_token)])


def _project_out(p: ProjectProfile) -> ProjectOut:
    return ProjectOut(
        project_id=p.project_id,
        project_code=p.project_code,
        company_name=p.company_name,
        short_name=p.short_name,
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
            select(TaskDetail.stage_id, func.count()).group_by(TaskDetail.stage_id)
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
        select(func.count()).select_from(TaskDetail).where(TaskDetail.stage_id == stage_id)
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
def list_stage_tasks(stage_id: int, db: Session = Depends(get_db)) -> list[TaskOut]:
    if not db.get(StageMap, stage_id):
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "阶段不存在"},
        )
    tasks = (
        db.execute(
            select(TaskDetail)
            .where(TaskDetail.stage_id == stage_id)
            .order_by(TaskDetail.sort_order)
        )
        .scalars()
        .all()
    )
    return [TaskOut.model_validate(t) for t in tasks]


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(
    stage_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[TaskOut]:
    q = select(TaskDetail).order_by(TaskDetail.sort_order)
    if stage_id is not None:
        q = q.where(TaskDetail.stage_id == stage_id)
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
        .order_by(ProjectProfile.project_id)
    )
    if status:
        query = query.where(ProjectProfile.project_status == status)
    if stage_id is not None:
        query = query.where(ProjectProfile.current_stage_id == stage_id)
    if building:
        query = query.where(ProjectProfile.building == building)
    if q:
        like = f"%{q}%"
        query = query.where(
            (ProjectProfile.project_code.like(like))
            | (ProjectProfile.company_name.like(like))
            | (ProjectProfile.short_name.like(like))
        )
    projects = db.execute(query).scalars().unique().all()
    return [_project_out(p) for p in projects]


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)) -> ProjectOut:
    p = get_project_or_none(db, project_id)
    if not p:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "企业不存在"},
        )
    return _project_out(p)


@router.get("/projects/{project_id}/progress", response_model=list[ProgressOut])
def project_progress(project_id: int, db: Session = Depends(get_db)) -> list[ProgressOut]:
    if not db.get(ProjectProfile, project_id):
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "企业不存在"},
        )
    rows = db.execute(
        select(ProjectProgress, TaskDetail)
        .join(TaskDetail, TaskDetail.task_id == ProjectProgress.task_id)
        .where(ProjectProgress.project_id == project_id)
        .order_by(TaskDetail.sort_order)
    ).all()
    return [
        ProgressOut(
            progress_id=pg.progress_id,
            project_id=pg.project_id,
            task_id=pg.task_id,
            task_code=td.task_code,
            task_name=td.task_name,
            stage_id=td.stage_id,
            status=pg.status,
            assigned_to=pg.assigned_to,
            completed_at=pg.completed_at,
            blocker_note=pg.blocker_note,
            critical_path=td.critical_path,
        )
        for pg, td in rows
    ]


@router.get("/projects/{project_id}/critical-path", response_model=CriticalPathOut)
def project_critical_path(project_id: int, db: Session = Depends(get_db)) -> CriticalPathOut:
    p = get_project_or_none(db, project_id)
    if not p:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "企业不存在"},
        )
    return build_critical_path(db, p)


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
    projects = db.execute(select(ProjectProfile)).scalars().all()
    by_status: dict[str, int] = {}
    by_stage: dict[str, int] = {}
    for p in projects:
        by_status[p.project_status] = by_status.get(p.project_status, 0) + 1
        if p.current_stage_id:
            stage = db.get(StageMap, p.current_stage_id)
            name = stage.stage_name if stage else str(p.current_stage_id)
            by_stage[name] = by_stage.get(name, 0) + 1
    blockers = list_blockers(db)
    return DashboardSummary(
        total_projects=len(projects),
        by_status=by_status,
        by_stage=by_stage,
        blockers=blockers,
    )


@router.post("/_write-guard")
def write_guard_stub(_body: WriteStubIn) -> dict:
    """Phase B: write not enabled; router-level auth still applies (B-T6)."""
    raise HTTPException(
        501,
        detail={
            "error": True,
            "code": "ERR_NOT_IMPLEMENTED",
            "message": "写入接口在 Phase C 开放",
        },
    )


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
