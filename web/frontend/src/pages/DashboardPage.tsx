import { useEffect, useMemo, useState } from "react";
import { Alert, Progress, Skeleton, Space, Table, Tabs, Tag } from "antd";
import { Link } from "react-router-dom";
import {
  api,
  type ComplianceCell,
  type ComplianceMatrix,
  type DashboardProject,
  type DashboardSummary,
  type DelayedTask,
} from "../api/client";
import "./DashboardPage.css";

const STAGES = [
  { id: 0, name: "初步意向", owner: "园区协调", days: 7, critical: "normal" },
  { id: 1, name: "项目准入", owner: "园区协调", days: 12, critical: "critical" },
  { id: 2, name: "厂房移交", owner: "客户主导", days: 15, critical: "critical" },
  { id: 3, name: "前期审批准备", owner: "客户主导", days: 120, critical: "critical" },
  { id: 4, name: "公用工程合同", owner: "园区协调", days: 30, critical: "important" },
  { id: 5, name: "施工审批", owner: "政府审批", days: 45, critical: "critical" },
  { id: 6, name: "项目施工及验收", owner: "客户主导", days: 120, critical: "critical" },
  { id: 7, name: "试生产准备", owner: "客户主导", days: 37, critical: "critical" },
  { id: 8, name: "三同时验收", owner: "政府审批", days: 68, critical: "critical" },
  { id: 9, name: "正式投用", owner: "客户主导", days: 7, critical: "normal" },
] as const;

const ownerByStage = new Map<number, string>(
  STAGES.map((stage) => [stage.id, stage.owner]),
);

const CELL_META: Record<
  ComplianceCell["status"],
  { icon: string; label: string; className: string }
> = {
  pass: { icon: "✓", label: "已通过", className: "is-pass" },
  doing: { icon: "◐", label: "进行中", className: "is-doing" },
  overdue: { icon: "!", label: "逾期", className: "is-overdue" },
  blocker: { icon: "⛔", label: "卡点", className: "is-blocker" },
  todo: { icon: "○", label: "待开始", className: "is-todo" },
  none: { icon: "–", label: "无记录", className: "is-none" },
};

function overdueDays(date: string): number {
  const planned = new Date(`${date}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.max(0, Math.round((today.getTime() - planned.getTime()) / 86400000));
}

function taskType(code?: string | null) {
  if (code?.startsWith("3.2")) return { label: "安评", color: "red" };
  if (code?.startsWith("3.3")) return { label: "环评", color: "orange" };
  if (code?.startsWith("3.4")) return { label: "卫评", color: "orange" };
  if (code?.startsWith("6.4")) return { label: "验收", color: "blue" };
  if (code?.startsWith("7.")) return { label: "试生产", color: "blue" };
  if (code?.startsWith("8.2")) return { label: "三同时", color: "red" };
  return { label: "其他", color: "default" };
}

type DashboardProjectView = DashboardProject & {
  delayedTasks: DelayedTask[];
  maxOverdueDays: number;
  worstTask: DelayedTask | null;
  riskScore: number;
};

function projectColumns() {
  return [
    {
      title: "项目",
      dataIndex: "project_code",
      width: 100,
      render: (_: string, row: DashboardProjectView) => (
        <Link className="dashboard-code" to={`/ops/projects/${row.project_id}`}>
          {row.project_code}
        </Link>
      ),
    },
    {
      title: "企业 / 楼宇",
      width: 160,
      render: (_: unknown, row: DashboardProjectView) => (
        <div>
          <strong>{row.short_name || row.company_name || row.project_code}</strong>
          <div className="dashboard-secondary">{row.building || "—"}</div>
        </div>
      ),
    },
    {
      title: "当前阶段",
      dataIndex: "current_stage_name",
      width: 190,
      render: (value: string | null) => <Tag color="blue">{value || "未设置"}</Tag>,
    },
    {
      title: "进度",
      dataIndex: "progress_percent",
      width: 170,
      render: (value: number) => (
        <Progress
          percent={value}
          size="small"
          strokeColor={value >= 91 ? "#047857" : value >= 61 ? "#0b5fff" : "#d97706"}
        />
      ),
    },
    {
      title: "健康度",
      width: 150,
      render: (_: unknown, row: DashboardProjectView) => (
        <Space size={4} wrap>
          {row.flags.blocker && <Tag color="error">卡点</Tag>}
          {row.flags.delayed && <Tag color="error">延期</Tag>}
          {row.flags.stalled && <Tag color="warning">周报异常</Tag>}
          {!row.flags.blocker && !row.flags.delayed && !row.flags.stalled && (
            <Tag color="success">正常</Tag>
          )}
        </Space>
      ),
    },
    {
      title: "逾期任务",
      width: 110,
      render: (_: unknown, row: DashboardProjectView) =>
        row.delayedTasks.length > 0 ? (
          <div>
            <strong className="dashboard-danger">{row.delayedTasks.length} 条</strong>
            <div className="dashboard-secondary">最长 {row.maxOverdueDays} 天</div>
          </div>
        ) : (
          "—"
        ),
    },
    {
      title: "操作",
      width: 70,
      fixed: "right" as const,
      render: (_: unknown, row: DashboardProjectView) => (
        <Link to={`/ops/projects/${row.project_id}`}>详情</Link>
      ),
    },
  ];
}

function ComplianceMatrixPanel({ matrix }: { matrix: ComplianceMatrix }) {
  return (
    <div className="dashboard-compliance">
      <div className="dashboard-table">
        <table className="dashboard-matrix">
          <thead>
            <tr>
              <th>项目</th>
              {matrix.columns.map((column) => (
                <th key={column.key}>
                  {column.label}
                  <span>{column.sub}</span>
                </th>
              ))}
              <th>当前阶段</th>
            </tr>
          </thead>
          <tbody>
            {matrix.rows.map((row) => (
              <tr key={row.project_id}>
                <td>
                  <Link to={`/ops/projects/${row.project_id}`}>
                    <strong>{row.short_name || row.project_code}</strong>
                  </Link>
                  <div className="dashboard-code dashboard-secondary">
                    {row.project_code}
                  </div>
                </td>
                {matrix.columns.map((column) => {
                  const cell = row.cells[column.key];
                  const meta = CELL_META[cell?.status ?? "none"];
                  const title = [
                    column.label,
                    meta.label,
                    cell?.task_code,
                    cell?.task_name,
                    cell?.planned_end ? `计划 ${cell.planned_end}` : null,
                    cell?.overdue_days != null ? `逾期 ${cell.overdue_days} 天` : null,
                    cell?.note,
                  ]
                    .filter(Boolean)
                    .join(" · ");
                  const body = (
                    <span className={`dashboard-matrix-cell ${meta.className}`} title={title}>
                      {meta.icon}
                    </span>
                  );
                  return (
                    <td key={column.key}>
                      {cell?.task_id ? (
                        <Link
                          to={`/ops/projects/${row.project_id}/tasks/${cell.task_id}`}
                        >
                          {body}
                        </Link>
                      ) : (
                        body
                      )}
                    </td>
                  );
                })}
                <td className="dashboard-secondary">
                  {row.current_stage_name || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="dashboard-matrix-legend">
        {Object.entries(CELL_META).map(([status, meta]) => (
          <span key={status}>
            <i className={`dashboard-matrix-cell ${meta.className}`}>{meta.icon}</i>
            {meta.label}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("attention");

  useEffect(() => {
    api
      .get<DashboardSummary>("/api/ops/dashboard/summary")
      .then((response) => setData(response.data))
      .catch((e) => setError(e.message));
  }, []);

  const view = useMemo(() => {
    if (!data) return null;
    const tasksByProject = new Map<number, DelayedTask[]>();
    for (const task of data.delayed_tasks ?? []) {
      const tasks = tasksByProject.get(task.project_id) ?? [];
      tasks.push(task);
      tasksByProject.set(task.project_id, tasks);
    }

    const projects: DashboardProjectView[] = (data.projects ?? []).map((project) => {
      const delayedTasks = tasksByProject.get(project.project_id) ?? [];
      const sortedTasks = delayedTasks
        .slice()
        .sort((a, b) => overdueDays(b.planned_end) - overdueDays(a.planned_end));
      const maxOverdueDays = sortedTasks[0] ? overdueDays(sortedTasks[0].planned_end) : 0;
      return {
        ...project,
        delayedTasks,
        maxOverdueDays,
        worstTask: sortedTasks[0] ?? null,
        riskScore:
          (project.flags.blocker ? 1000 : 0) +
          delayedTasks.length * 10 +
          maxOverdueDays +
          (project.flags.stalled ? 30 : 0),
      };
    });

    return {
      projects,
      delayedTasks: (data.delayed_tasks ?? [])
        .slice()
        .sort((a, b) => overdueDays(b.planned_end) - overdueDays(a.planned_end)),
      healthyProjects: projects.filter(
        (project) =>
          !project.flags.blocker && !project.flags.delayed && !project.flags.stalled,
      ).length,
      attentionProjects: projects
        .filter((project) => project.flags.blocker || project.flags.delayed)
        .sort((a, b) => b.riskScore - a.riskScore),
      priorityProjects: projects
        .filter((project) => project.riskScore > 30)
        .sort((a, b) => b.riskScore - a.riskScore)
        .slice(0, 6),
    };
  }, [data]);

  if (error) return <Alert type="error" showIcon message="看板加载失败" description={error} />;
  if (!data || !view) return <Skeleton active paragraph={{ rows: 12 }} />;

  const phases = data.phase_buckets;
  const counts = data.counts;
  const stageCounts = new Map<number, number>();
  for (const project of view.projects) {
    if (project.current_stage_id !== null) {
      stageCounts.set(
        project.current_stage_id,
        (stageCounts.get(project.current_stage_id) ?? 0) + 1,
      );
    }
  }

  const switchTo = (tab: string) => {
    setActiveTab(tab);
    requestAnimationFrame(() =>
      document.getElementById("dashboard-details")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      }),
    );
  };

  const projectTable = (projects: DashboardProjectView[]) => (
    <div className="dashboard-table">
      <Table
        rowKey="project_id"
        size="small"
        dataSource={projects}
        columns={projectColumns()}
        scroll={{ x: 1050 }}
        pagination={{ pageSize: 10, hideOnSinglePage: true }}
      />
    </div>
  );

  const overdueTable = (
    <div className="dashboard-table">
      <Table
        rowKey={(task) => `${task.project_id}-${task.task_id}`}
        size="small"
        dataSource={view.delayedTasks}
        scroll={{ x: 1050 }}
        pagination={{ pageSize: 12, hideOnSinglePage: true }}
        columns={[
          {
            title: "逾期",
            width: 80,
            render: (_: unknown, task: DelayedTask) => (
              <strong className="dashboard-danger">{overdueDays(task.planned_end)} 天</strong>
            ),
          },
          {
            title: "任务",
            width: 360,
            render: (_: unknown, task: DelayedTask) => (
              <div>
                <span className="dashboard-code">{task.task_code}</span> {task.task}
                {task.note && <div className="dashboard-task-note">备注：{task.note}</div>}
              </div>
            ),
          },
          {
            title: "项目",
            width: 130,
            render: (_: unknown, task: DelayedTask) => {
              const project = view.projects.find(
                (item) => item.project_id === task.project_id,
              );
              return (
                <Link to={`/ops/projects/${task.project_id}`}>
                  {project?.short_name || task.project_code}
                </Link>
              );
            },
          },
          {
            title: "类型",
            width: 90,
            render: (_: unknown, task: DelayedTask) => {
              const type = taskType(task.task_code);
              return <Tag color={type.color}>{type.label}</Tag>;
            },
          },
          { title: "计划完成", dataIndex: "planned_end", width: 120 },
          { title: "状态", dataIndex: "status", width: 100 },
          {
            title: "处理",
            width: 70,
            fixed: "right",
            render: (_: unknown, task: DelayedTask) => (
              <Link to={`/ops/projects/${task.project_id}/tasks/${task.task_id}`}>
                更新
              </Link>
            ),
          },
        ]}
      />
    </div>
  );

  return (
    <div className="dashboard">
      <div className="dashboard-glance">
        <div className="dashboard-kpis">
          <div className="dashboard-kpi is-info">
            <span>在管项目</span>
            <strong>{data.total_projects}</strong>
            <small>
              准入 {phases.access_projects} · 建设 {phases.construction_projects} ·
              运营 {phases.operation_projects}
            </small>
          </div>
          <div className="dashboard-kpi is-health">
            <span>健康项目</span>
            <strong>
              {view.healthyProjects}<i>/{data.total_projects}</i>
            </strong>
            <small>无延期 · 无阻塞 · 周报正常</small>
          </div>
          <div className="dashboard-kpi is-danger">
            <span>延期项目</span>
            <strong>
              {counts.delayed_projects}<i>/{data.total_projects}</i>
            </strong>
            <small>{view.delayedTasks.length} 条逾期任务</small>
          </div>
          <div className="dashboard-kpi is-warning">
            <span>
              周报异常 <Tag>机制</Tag>
            </span>
            <strong>
              {counts.stalled_projects}<i>/{data.total_projects}</i>
            </strong>
            <small>未回写或超过停滞阈值</small>
          </div>
        </div>

        <div className="dashboard-pipeline-wrap">
          <div className="dashboard-buckets">
            <div><span>准入</span><strong>{phases.access_projects}</strong></div>
            <div><span>建设</span><strong>{phases.construction_projects}</strong><small>主战场</small></div>
            <div><span>运营</span><strong>{phases.operation_projects}</strong></div>
          </div>
          <div className="dashboard-pipeline">
            {STAGES.map((stage) => {
              const count = stageCounts.get(stage.id) ?? 0;
              const crowded = count >= 4;
              return (
                <div
                  className={`dashboard-stage ${count ? "has-project" : ""} ${crowded ? "is-crowded" : ""}`}
                  key={stage.id}
                >
                  <div className="dashboard-stage-dot">{count}</div>
                  <div className="dashboard-stage-name">
                    <i className={`critical-${stage.critical}`} />
                    {stage.name}
                  </div>
                  <small>{stage.days} 天 · {stage.owner}</small>
                  {crowded && <Tag color="error">拥堵</Tag>}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="dashboard-workbench" id="dashboard-details">
        <section className="dashboard-card dashboard-queue">
          <div className="dashboard-panel-head">
            <h2>优先处理</h2>
            <a onClick={() => switchTo("overdue")}>全部逾期 →</a>
          </div>
          <div className="dashboard-priority-list">
            {view.priorityProjects.map((project) => {
              const task = project.worstTask;
              const type = taskType(task?.task_code);
              return (
                <div
                  className={`dashboard-priority ${project.flags.blocker || project.maxOverdueDays > 180 ? "is-severe" : ""}`}
                  key={project.project_id}
                >
                  <div className="dashboard-priority-title">
                    <strong>{project.short_name || project.project_code}</strong>
                    <span className="dashboard-code">{project.project_code}</span>
                    <span className="dashboard-secondary">{project.building || "—"}</span>
                    {project.flags.blocker && <Tag color="error">卡点</Tag>}
                    {project.delayedTasks.length > 0 && (
                      <Tag color="error">逾期 {project.delayedTasks.length} 条</Tag>
                    )}
                    {project.flags.stalled && <Tag>周报异常</Tag>}
                    <Tag color="blue">
                      {project.current_stage_id === null
                        ? "未设置"
                        : ownerByStage.get(project.current_stage_id)}
                    </Tag>
                  </div>
                  <Space size={8}>
                    <Link to={`/ops/projects/${project.project_id}`}>进项目</Link>
                    {task && (
                      <Link
                        to={`/ops/projects/${project.project_id}/tasks/${task.task_id}`}
                      >
                        处理
                      </Link>
                    )}
                  </Space>
                  {task && (
                    <div className="dashboard-priority-detail">
                      最严重：<Tag color={type.color}>{type.label}</Tag>
                      <span className="dashboard-code">{task.task_code}</span> {task.task}
                      <span> · 计划 {task.planned_end} · </span>
                      <strong className="dashboard-danger">
                        已逾期 {project.maxOverdueDays} 天
                      </strong>
                    </div>
                  )}
                  {task?.note && (
                    <div className="dashboard-task-note">备注：{task.note}</div>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        <section className="dashboard-card dashboard-tabs-card">
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={[
              {
                key: "attention",
                label: `需关注 ${view.attentionProjects.length}`,
                children: projectTable(view.attentionProjects),
              },
              {
                key: "compliance",
                label: `三评三同时 ${(data.compliance_matrix?.columns ?? []).length}`,
                children: (
                  <ComplianceMatrixPanel
                    matrix={data.compliance_matrix ?? { columns: [], rows: [] }}
                  />
                ),
              },
              {
                key: "overdue",
                label: `逾期 ${view.delayedTasks.length}`,
                children: overdueTable,
              },
              {
                key: "all",
                label: `全部 ${view.projects.length}`,
                children: projectTable(view.projects),
              },
            ]}
          />
        </section>
      </div>
    </div>
  );
}
