"""运营 Dashboard 汇总服务。"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from models import ProgressJournal, ProjectProgress, ProjectProfile, StageMap, TaskDetail
from schemas import (
    BlockerOut,
    ComplianceCellOut,
    ComplianceColumnOut,
    ComplianceMatrixOut,
    ComplianceRowOut,
    DashboardCounts,
    DashboardPhaseBuckets,
    DashboardProjectOut,
    DashboardSummary,
    DelayedTaskOut,
    ProjectIssueFlags,
)
from services.progress_service import ensure_current_stages
from services.settings_service import (
    get_journal_alert,
    is_journal_stalled,
    journal_alert_label,
)

DONE_STATUSES = frozenset({"已完成", "已跳过"})
# Dashboard 阶段分布与阶段地图一致，但不含「公用工程及服务类合同签定」
DASHBOARD_EXCLUDE_STAGE_IDS = frozenset({4})
ACCESS_STAGE_IDS = frozenset({0, 1})
CONSTRUCTION_STAGE_IDS = frozenset({2, 3, 4, 5, 6, 7})
OPERATION_STAGE_IDS = frozenset({8, 9})

# 三评三同时列映射（task_code 以当前 task_detail 为准）
COMPLIANCE_COLUMNS: tuple[ComplianceColumnOut, ...] = (
    ComplianceColumnOut(
        key="safety_eval",
        label="安全预评价",
        sub="安评 · 3.2.3/4 + 3.2.7",
        codes=["3.2.3", "3.2.4", "3.2.7"],
    ),
    ComplianceColumnOut(
        key="safety_design",
        label="安全设施设计专篇",
        sub="安设 · 3.2.5/6",
        codes=["3.2.5", "3.2.6"],
    ),
    ComplianceColumnOut(
        key="env_eval",
        label="环境影响评价",
        sub="环评 · 3.3.1/2/3",
        codes=["3.3.1", "3.3.2", "3.3.3"],
    ),
    ComplianceColumnOut(
        key="fire",
        label="消防验收",
        sub="6.4.2",
        codes=["6.4.2"],
    ),
    ComplianceColumnOut(
        key="trial_review",
        label="试生产方案评审",
        sub="试生产 · 7.1.1/2/3",
        codes=["7.1.1", "7.1.2", "7.1.3"],
    ),
    ComplianceColumnOut(
        key="safety_accept",
        label="竣工安全验收",
        sub="三同时 · 8.2.1",
        codes=["8.2.1"],
    ),
    ComplianceColumnOut(
        key="env_accept",
        label="竣工环保验收",
        sub="三同时 · 8.2.2",
        codes=["8.2.2"],
    ),
)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    s = value.strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _compliance_cell(
    rows: list[tuple[ProjectProgress, TaskDetail]],
    today: date,
) -> ComplianceCellOut:
    """把同一合规列下的多条进度收成一个单元格。

    优先级：卡点 > 逾期 > 进行中 > 待开始 > 已通过 > 无记录。
    """
    if not rows:
        return ComplianceCellOut(status="none")

    def pack(
        status: str,
        pg: ProjectProgress,
        td: TaskDetail,
        overdue: int | None = None,
    ) -> ComplianceCellOut:
        pe = _parse_date(pg.planned_end)
        return ComplianceCellOut(
            status=status,
            task_id=td.task_id,
            task_code=td.task_code,
            task_name=td.task_name,
            planned_end=pe.isoformat() if pe else None,
            overdue_days=overdue,
            note=pg.blocker_note or pg.notes,
        )

    for pg, td in rows:
        if pg.status == "卡点":
            pe = _parse_date(pg.planned_end)
            overdue = (today - pe).days if pe and pe < today else None
            return pack("blocker", pg, td, overdue)

    overdue_candidates: list[tuple[int, ProjectProgress, TaskDetail]] = []
    for pg, td in rows:
        if pg.status in DONE_STATUSES:
            continue
        pe = _parse_date(pg.planned_end)
        if pe is not None and pe < today:
            overdue_candidates.append(((today - pe).days, pg, td))
    if overdue_candidates:
        overdue_candidates.sort(key=lambda x: x[0], reverse=True)
        days, pg, td = overdue_candidates[0]
        return pack("overdue", pg, td, days)

    for pg, td in rows:
        if pg.status == "进行中":
            return pack("doing", pg, td)

    for pg, td in rows:
        if pg.status == "待开始":
            return pack("todo", pg, td)

    if all(pg.status in DONE_STATUSES for pg, _ in rows):
        # 取编号最大的已完成任务，便于跳到该节点
        pg, td = max(rows, key=lambda item: item[1].task_code or "")
        return pack("pass", pg, td)

    pg, td = rows[0]
    return pack("todo", pg, td)


def _build_compliance_matrix(
    db: Session,
    project_outs: list[DashboardProjectOut],
    today: date,
) -> ComplianceMatrixOut:
    all_codes = [code for col in COMPLIANCE_COLUMNS for code in col.codes]
    progress_rows = db.execute(
        select(ProjectProgress, TaskDetail)
        .join(TaskDetail, TaskDetail.task_id == ProjectProgress.task_id)
        .where(
            TaskDetail.is_active == 1,
            TaskDetail.task_code.in_(all_codes),
        )
    ).all()

    by_project: dict[int, list[tuple[ProjectProgress, TaskDetail]]] = {}
    for pg, td in progress_rows:
        by_project.setdefault(pg.project_id, []).append((pg, td))

    rows: list[ComplianceRowOut] = []
    for project in project_outs:
        items = by_project.get(project.project_id, [])
        cells: dict[str, ComplianceCellOut] = {}
        for col in COMPLIANCE_COLUMNS:
            matched = [
                (pg, td)
                for pg, td in items
                if td.task_code in col.codes
            ]
            # 同列内按 task_code 排序，保证展示稳定
            matched.sort(key=lambda item: item[1].task_code or "")
            cells[col.key] = _compliance_cell(matched, today)
        rows.append(
            ComplianceRowOut(
                project_id=project.project_id,
                project_code=project.project_code,
                short_name=project.short_name,
                current_stage_name=project.current_stage_name,
                cells=cells,
            )
        )

    return ComplianceMatrixOut(columns=list(COMPLIANCE_COLUMNS), rows=rows)


def build_dashboard_summary(db: Session) -> DashboardSummary:
    today = date.today()
    alert_rule = get_journal_alert(db)
    alert_out = alert_rule.model_copy(
        update={"label": journal_alert_label(alert_rule)}
    )

    projects = ensure_current_stages(
        db,
        list(
            db.execute(
                select(ProjectProfile)
                .options(joinedload(ProjectProfile.current_stage))
                .order_by(ProjectProfile.project_id)
            )
            .scalars()
            .unique()
            .all()
        ),
    )
    stages = (
        db.execute(select(StageMap).order_by(StageMap.sort_order)).scalars().all()
    )
    stage_names = {s.stage_id: s.stage_name for s in stages}
    # 按 sort_order；排除公用工程阶段（与阶段地图展示口径一致）
    chart_stages = [s for s in stages if s.stage_id not in DASHBOARD_EXCLUDE_STAGE_IDS]

    by_status: dict[str, int] = {}
    by_stage: dict[str, int] = {s.stage_name: 0 for s in chart_stages}
    access_n = construction_n = operation_n = 0
    for p in projects:
        by_status[p.project_status] = by_status.get(p.project_status, 0) + 1
        sid = p.current_stage_id
        if sid is not None and sid not in DASHBOARD_EXCLUDE_STAGE_IDS:
            name = stage_names.get(sid) or str(sid)
            if name in by_stage:
                by_stage[name] = by_stage[name] + 1
            else:
                by_stage[name] = 1
        if sid in ACCESS_STAGE_IDS:
            access_n += 1
        elif sid in CONSTRUCTION_STAGE_IDS:
            construction_n += 1
        elif sid in OPERATION_STAGE_IDS:
            operation_n += 1

    # 阶段分布：隐去项目数为 0 的阶段（保持 sort_order）
    by_stage = {k: v for k, v in by_stage.items() if v > 0}
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
        is_stalled = is_journal_stalled(
            project_status=p.project_status,
            last_week=str(last_week) if last_week else None,
            rule=alert_rule,
            today=today,
        )
        if is_stalled:
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
                short_name=p.short_name,
                building=p.building,
                current_stage_id=p.current_stage_id,
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

    # 项目清单：阶段从后到前；同阶段进度高→低
    stage_sort = {s.stage_id: s.sort_order for s in stages}

    def _project_sort_key(row: DashboardProjectOut) -> tuple:
        sid = row.current_stage_id
        order = stage_sort.get(sid, -1) if sid is not None else -1
        return (-order, -(row.progress_percent or 0), row.project_code)

    project_outs.sort(key=_project_sort_key)

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
        phase_buckets=DashboardPhaseBuckets(
            access_projects=access_n,
            construction_projects=construction_n,
            operation_projects=operation_n,
        ),
        compliance_matrix=_build_compliance_matrix(db, project_outs, today),
        journal_alert=alert_out,
    )
