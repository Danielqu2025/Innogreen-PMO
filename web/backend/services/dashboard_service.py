"""运营 Dashboard 汇总服务。"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from models import ProgressJournal, ProjectProgress, ProjectProfile, StageMap, TaskDetail
from schemas import (
    BlockerOut,
    DashboardCounts,
    DashboardProjectOut,
    DashboardSummary,
    DelayedTaskOut,
    ProjectIssueFlags,
)

STALL_DAYS = 14
DONE_STATUSES = frozenset({"已完成", "已跳过"})
# Dashboard 阶段分布与阶段地图一致，但不含「公用工程及服务类合同签定」
DASHBOARD_EXCLUDE_STAGE_IDS = frozenset({3})


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    s = value.strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def build_dashboard_summary(db: Session) -> DashboardSummary:
    today = date.today()
    stall_before = (today - timedelta(days=STALL_DAYS)).isoformat()

    projects = (
        db.execute(
            select(ProjectProfile)
            .options(joinedload(ProjectProfile.current_stage))
            .order_by(ProjectProfile.project_id)
        )
        .scalars()
        .unique()
        .all()
    )
    stages = (
        db.execute(select(StageMap).order_by(StageMap.sort_order)).scalars().all()
    )
    stage_names = {s.stage_id: s.stage_name for s in stages}
    # 按 sort_order；排除公用工程阶段（与阶段地图展示口径一致）
    chart_stages = [s for s in stages if s.stage_id not in DASHBOARD_EXCLUDE_STAGE_IDS]

    by_status: dict[str, int] = {}
    by_stage: dict[str, int] = {s.stage_name: 0 for s in chart_stages}
    for p in projects:
        by_status[p.project_status] = by_status.get(p.project_status, 0) + 1
        if p.current_stage_id and p.current_stage_id not in DASHBOARD_EXCLUDE_STAGE_IDS:
            name = stage_names.get(p.current_stage_id) or str(p.current_stage_id)
            if name in by_stage:
                by_stage[name] = by_stage[name] + 1
            else:
                by_stage[name] = 1

    # blockers
    blocker_rows = db.execute(
        select(ProjectProgress, ProjectProfile, TaskDetail)
        .join(ProjectProfile, ProjectProfile.project_id == ProjectProgress.project_id)
        .join(TaskDetail, TaskDetail.task_id == ProjectProgress.task_id)
        .where(
            ProjectProgress.status == "卡点",
            TaskDetail.is_active == 1,
        )
        .order_by(ProjectProfile.project_id, TaskDetail.sort_order)
    ).all()
    blockers = [
        BlockerOut(
            project_id=pp.project_id,
            project_code=pp.project_code,
            project=pp.company_name or pp.project_code,
            task_id=td.task_id,
            task_code=td.task_code,
            task=td.task_name,
            note=pg.blocker_note,
            project_status=pp.project_status,
        )
        for pg, pp, td in blocker_rows
    ]
    blocker_project_ids = {b.project_id for b in blockers}

    # delayed tasks
    progress_rows = db.execute(
        select(ProjectProgress, ProjectProfile, TaskDetail)
        .join(ProjectProfile, ProjectProfile.project_id == ProjectProgress.project_id)
        .join(TaskDetail, TaskDetail.task_id == ProjectProgress.task_id)
        .where(
            TaskDetail.is_active == 1,
            ProjectProgress.planned_end.is_not(None),
            ProjectProgress.status.notin_(DONE_STATUSES),
        )
        .order_by(ProjectProgress.planned_end, ProjectProfile.project_id)
    ).all()
    delayed_tasks: list[DelayedTaskOut] = []
    delayed_project_ids: set[int] = set()
    for pg, pp, td in progress_rows:
        pe = _parse_date(pg.planned_end)
        if pe is None or pe >= today:
            continue
        delayed_project_ids.add(pp.project_id)
        delayed_tasks.append(
            DelayedTaskOut(
                project_id=pp.project_id,
                project_code=pp.project_code,
                project=pp.company_name or pp.project_code,
                task_id=td.task_id,
                task_code=td.task_code,
                task=td.task_name,
                planned_end=pe.isoformat(),
                status=pg.status,
                note=pg.blocker_note or pg.notes,
            )
        )

    # last journal week per project
    journal_max = dict(
        db.execute(
            select(
                ProgressJournal.project_id,
                func.max(ProgressJournal.week_start),
            ).group_by(ProgressJournal.project_id)
        ).all()
    )

    project_outs: list[DashboardProjectOut] = []
    stalled_project_ids: set[int] = set()
    for p in projects:
        last_week = journal_max.get(p.project_id)
        is_blocker = p.project_id in blocker_project_ids
        is_delayed = p.project_id in delayed_project_ids
        is_stalled = False
        if p.project_status == "进行中":
            if last_week is None or str(last_week) < stall_before:
                is_stalled = True
                stalled_project_ids.add(p.project_id)

        stage_name = None
        if p.current_stage:
            stage_name = p.current_stage.stage_name
        elif p.current_stage_id:
            stage_name = stage_names.get(p.current_stage_id)

        project_outs.append(
            DashboardProjectOut(
                project_id=p.project_id,
                project_code=p.project_code,
                company_name=p.company_name,
                current_stage_name=stage_name,
                progress_percent=p.progress_percent or 0,
                project_status=p.project_status,
                flags=ProjectIssueFlags(
                    blocker=is_blocker,
                    delayed=is_delayed,
                    stalled=is_stalled,
                ),
                last_journal_week=str(last_week) if last_week else None,
            )
        )

    return DashboardSummary(
        total_projects=len(projects),
        by_status=by_status,
        by_stage=by_stage,
        blockers=blockers,
        projects=project_outs,
        delayed_tasks=delayed_tasks,
        counts=DashboardCounts(
            blocker_projects=len(blocker_project_ids),
            delayed_projects=len(delayed_project_ids),
            stalled_projects=len(stalled_project_ids),
        ),
    )
