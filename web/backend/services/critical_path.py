from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from models import ProjectProgress, ProjectProfile, StageMap, TaskDependency, TaskDetail
from schemas import CriticalPathEdge, CriticalPathNode, CriticalPathOut


def build_critical_path(db: Session, project: ProjectProfile) -> CriticalPathOut:
    """Critical tasks (🔴) with deps, annotated by project progress."""
    tasks = (
        db.execute(
            select(TaskDetail)
            .where(TaskDetail.critical_path == "🔴")
            .order_by(TaskDetail.sort_order)
        )
        .scalars()
        .all()
    )
    task_ids = {t.task_id for t in tasks}
    stages = {
        s.stage_id: s
        for s in db.execute(select(StageMap)).scalars().all()
    }
    progress_map = {
        p.task_id: p
        for p in db.execute(
            select(ProjectProgress).where(ProjectProgress.project_id == project.project_id)
        )
        .scalars()
        .all()
    }

    nodes: list[CriticalPathNode] = []
    for t in tasks:
        stage = stages.get(t.stage_id)
        prog = progress_map.get(t.task_id)
        nodes.append(
            CriticalPathNode(
                task_id=t.task_id,
                task_code=t.task_code,
                task_name=t.task_name,
                stage_id=t.stage_id,
                stage_name=stage.stage_name if stage else "",
                critical_path=t.critical_path,
                status=prog.status if prog else "待开始",
                blocker_note=prog.blocker_note if prog else None,
            )
        )

    deps = (
        db.execute(
            select(TaskDependency).where(
                TaskDependency.task_id.in_(task_ids),
                TaskDependency.depends_on.in_(task_ids),
            )
        )
        .scalars()
        .all()
    )
    edges = [
        CriticalPathEdge(
            from_task_id=d.depends_on,
            to_task_id=d.task_id,
            dependency_type=d.dependency_type,
        )
        for d in deps
    ]

    return CriticalPathOut(
        project_id=project.project_id,
        project_code=project.project_code,
        nodes=nodes,
        edges=edges,
    )


def get_project_or_none(db: Session, project_id: int) -> ProjectProfile | None:
    return db.execute(
        select(ProjectProfile)
        .options(joinedload(ProjectProfile.current_stage))
        .where(ProjectProfile.project_id == project_id)
    ).scalar_one_or_none()
