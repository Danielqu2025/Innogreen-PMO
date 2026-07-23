import { useEffect, useState } from "react";
import {
  Alert,
  Col,
  List,
  Progress,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import { Link } from "react-router-dom";
import {
  api,
  type DashboardProject,
  type DashboardSummary,
} from "../api/client";

const statusColor: Record<string, string> = {
  卡点: "error",
  进行中: "processing",
  已完成: "success",
  未开始: "default",
  已退园: "default",
};

function StageBars({ byStage }: { byStage?: Record<string, number> }) {
  const entries = Object.entries(byStage ?? {}).filter(([, n]) => n > 0);
  if (entries.length === 0) {
    return <Typography.Text type="secondary">暂无阶段数据</Typography.Text>;
  }
  const max = Math.max(1, ...entries.map(([, n]) => n));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {entries.map(([name, count]) => (
        <div key={name}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              marginBottom: 4,
              fontSize: 13,
            }}
          >
            <span>{name}</span>
            <Typography.Text
              strong
              style={{ color: "rgba(0, 0, 0, 0.88)", fontSize: 15 }}
            >
              {count}
            </Typography.Text>
          </div>
          <Progress
            percent={Math.round((100 * count) / max)}
            showInfo={false}
            strokeColor="#1677ff"
            size="small"
          />
        </div>
      ))}
    </div>
  );
}

/** task_code 分段比较，从后到前（如 8.1 > 5.2.1） */
function cmpTaskCodeDesc(a?: string | null, b?: string | null): number {
  const parse = (code?: string | null) =>
    (code ?? "")
      .split(".")
      .filter(Boolean)
      .map((p) => {
        const n = Number(p);
        return Number.isFinite(n) ? n : 0;
      });
  const pa = parse(a);
  const pb = parse(b);
  const len = Math.max(pa.length, pb.length);
  for (let i = 0; i < len; i++) {
    const da = pa[i] ?? 0;
    const db = pb[i] ?? 0;
    if (da !== db) return db - da;
  }
  return 0;
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<DashboardSummary>("/api/ops/dashboard/summary")
      .then((r) => setData(r.data))
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <Alert type="error" message={error} />;
  if (!data) return <Typography.Text>加载中…</Typography.Text>;

  const projects = data.projects ?? [];
  const delayedTasks = data.delayed_tasks ?? [];
  const blockers = data.blockers ?? [];
  const phases = data.phase_buckets ?? {
    access_projects: 0,
    construction_projects: 0,
    operation_projects: 0,
  };

  // 与第1部分项目表同序；同项目内问题按 task_code 从后到前
  const projectOrder = new Map(projects.map((p, i) => [p.project_id, i]));
  const projectLabel = new Map(
    projects.map((p) => [p.project_id, p.short_name || p.project_code]),
  );

  const todoItems = [
    ...blockers.map((b) => ({
      key: `b-${b.project_id}-${b.task_id}`,
      kind: "卡点" as const,
      project_id: b.project_id,
      project_label: projectLabel.get(b.project_id) ?? b.project_code,
      task_id: b.task_id,
      task_code: b.task_code ?? null,
      title: `${b.task_code ?? ""} ${b.task}`.trim(),
      detail: b.note || "需处理卡点",
    })),
    ...delayedTasks.map((t) => ({
      key: `d-${t.project_id}-${t.task_id}`,
      kind: "延期" as const,
      project_id: t.project_id,
      project_label: projectLabel.get(t.project_id) ?? t.project_code,
      task_id: t.task_id,
      task_code: t.task_code ?? null,
      title: `${t.task_code ?? ""} ${t.task}`.trim(),
      detail: `计划完成 ${t.planned_end} · 当前 ${t.status}`,
    })),
  ].sort((a, b) => {
    const oa = projectOrder.get(a.project_id) ?? Number.MAX_SAFE_INTEGER;
    const ob = projectOrder.get(b.project_id) ?? Number.MAX_SAFE_INTEGER;
    if (oa !== ob) return oa - ob;
    const byCode = cmpTaskCodeDesc(a.task_code, b.task_code);
    if (byCode !== 0) return byCode;
    return a.kind.localeCompare(b.kind);
  });

  return (
    <div>
      {/* —— 1. 整体 —— */}
      <Typography.Title level={4} style={{ marginTop: 0 }}>
        1. 整体情况：各项目在哪一阶段
      </Typography.Title>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Statistic title="企业总数" value={data.total_projects} />
        </Col>
        <Col xs={12} sm={6}>
          <Statistic title="准入阶段项目" value={phases.access_projects} />
        </Col>
        <Col xs={12} sm={6}>
          <Statistic title="建设阶段项目" value={phases.construction_projects} />
        </Col>
        <Col xs={12} sm={6}>
          <Statistic title="投运阶段项目" value={phases.operation_projects} />
        </Col>
      </Row>

      <Row gutter={[24, 24]}>
        <Col xs={24} lg={10}>
          <Typography.Text strong>阶段分布</Typography.Text>
          <div style={{ marginTop: 12 }}>
            <StageBars byStage={data.by_stage} />
          </div>
        </Col>
        <Col xs={24} lg={14}>
          <Table
            size="small"
            rowKey="project_id"
            pagination={{ pageSize: 8, hideOnSinglePage: true }}
            dataSource={projects}
            columns={[
              {
                title: "项目",
                dataIndex: "short_name",
                render: (_: string | null, row: DashboardProject) => (
                  <Link to={`/ops/projects/${row.project_id}`}>
                    {row.short_name || row.project_code}
                  </Link>
                ),
              },
              {
                title: "楼栋号",
                dataIndex: "building",
                width: 100,
                render: (v: string | null) => v || "—",
              },
              {
                title: "当前阶段",
                dataIndex: "current_stage_name",
                ellipsis: true,
                render: (v: string | null) => v || "—",
              },
              {
                title: "进度",
                dataIndex: "progress_percent",
                width: 90,
                render: (v: number) => `${v}%`,
              },
              {
                title: "状态",
                dataIndex: "project_status",
                width: 90,
                render: (s: string) => (
                  <Tag color={statusColor[s] || "default"}>{s}</Tag>
                ),
              },
              {
                title: "风险",
                width: 160,
                render: (_: unknown, row: DashboardProject) => {
                  const flags = row.flags;
                  if (!flags?.blocker && !flags?.delayed && !flags?.stalled) {
                    return "—";
                  }
                  return (
                    <Space size={4} wrap>
                      {flags.blocker && <Tag color="error">卡点</Tag>}
                      {flags.delayed && <Tag color="warning">延期</Tag>}
                      {flags.stalled && <Tag>停滞</Tag>}
                    </Space>
                  );
                },
              },
            ]}
          />
        </Col>
      </Row>

      {/* —— 2. 待办 —— */}
      <Typography.Title level={4} style={{ marginTop: 32 }}>
        2. 待办问题：需要具体解决什么
      </Typography.Title>
      <List
        bordered
        size="small"
        locale={{ emptyText: "暂无待办（无卡点、无过期计划任务）" }}
        dataSource={todoItems}
        renderItem={(item) => (
          <List.Item
            actions={[
              <Link
                key="go"
                to={`/ops/projects/${item.project_id}/tasks/${item.task_id}`}
              >
                处理
              </Link>,
            ]}
          >
            <List.Item.Meta
              title={
                <Space>
                  <Tag color={item.kind === "卡点" ? "error" : "warning"}>
                    {item.kind}
                  </Tag>
                  <Link to={`/ops/projects/${item.project_id}`}>
                    {item.project_label}
                  </Link>
                  <span>{item.title}</span>
                </Space>
              }
              description={item.detail}
            />
          </List.Item>
        )}
      />
    </div>
  );
}
