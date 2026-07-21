import { useEffect, useMemo, useState } from "react";
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
            <Typography.Text type="secondary">{count}</Typography.Text>
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

function riskReason(p: DashboardProject): string {
  const parts: string[] = [];
  if (p.flags.blocker) parts.push("存在卡点任务");
  if (p.flags.delayed) parts.push("有任务计划完成日已过");
  if (p.flags.stalled) {
    parts.push(
      p.last_journal_week
        ? `周记停滞（最近 ${p.last_journal_week}）`
        : "无周记更新",
    );
  }
  return parts.join("；") || "—";
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

  const riskProjects = useMemo(() => {
    if (!data?.projects) return [];
    return data.projects.filter(
      (p) => p.flags?.blocker || p.flags?.delayed || p.flags?.stalled,
    );
  }, [data]);

  if (error) return <Alert type="error" message={error} />;
  if (!data) return <Typography.Text>加载中…</Typography.Text>;

  const projects = data.projects ?? [];
  const delayedTasks = data.delayed_tasks ?? [];
  const blockers = data.blockers ?? [];
  const counts = data.counts ?? {
    blocker_projects: 0,
    delayed_projects: 0,
    stalled_projects: 0,
  };
  const phases = data.phase_buckets ?? {
    access_projects: 0,
    construction_projects: 0,
    operation_projects: 0,
  };

  const todoItems = [
    ...blockers.map((b) => ({
      key: `b-${b.project_id}-${b.task_id}`,
      kind: "卡点" as const,
      project_id: b.project_id,
      project_code: b.project_code,
      task_id: b.task_id,
      title: `${b.task_code ?? ""} ${b.task}`.trim(),
      detail: b.note || "需处理卡点",
    })),
    ...delayedTasks.map((t) => ({
      key: `d-${t.project_id}-${t.task_id}`,
      kind: "延期" as const,
      project_id: t.project_id,
      project_code: t.project_code,
      task_id: t.task_id,
      title: `${t.task_code ?? ""} ${t.task}`.trim(),
      detail: `计划完成 ${t.planned_end} · 当前 ${t.status}`,
    })),
  ];

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
                dataIndex: "project_code",
                render: (code: string, row: DashboardProject) => (
                  <Link to={`/ops/projects/${row.project_id}`}>{code}</Link>
                ),
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
            ]}
          />
        </Col>
      </Row>

      {/* —— 2. 风险 —— */}
      <Typography.Title level={4} style={{ marginTop: 32 }}>
        2. 推进风险：延迟 / 停滞 / 卡点的项目
      </Typography.Title>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={8}>
          <Statistic
            title="卡点项目"
            value={counts.blocker_projects}
            valueStyle={{ color: "#cf1322" }}
          />
        </Col>
        <Col xs={8}>
          <Statistic
            title="延期项目"
            value={counts.delayed_projects}
            valueStyle={{ color: "#d48806" }}
          />
        </Col>
        <Col xs={8}>
          <Statistic title="停滞项目" value={counts.stalled_projects} />
        </Col>
      </Row>
      <Table
        size="small"
        rowKey="project_id"
        pagination={{ pageSize: 8, hideOnSinglePage: true }}
        locale={{ emptyText: "暂无风险项目" }}
        dataSource={riskProjects}
        columns={[
          {
            title: "项目",
            dataIndex: "project_code",
            width: 100,
            render: (code: string, row: DashboardProject) => (
              <Link to={`/ops/projects/${row.project_id}`}>{code}</Link>
            ),
          },
          {
            title: "风险",
            width: 200,
            render: (_: unknown, row: DashboardProject) => (
              <Space size={4} wrap>
                {row.flags.blocker && <Tag color="error">卡点</Tag>}
                {row.flags.delayed && <Tag color="warning">延期</Tag>}
                {row.flags.stalled && <Tag>停滞</Tag>}
              </Space>
            ),
          },
          {
            title: "阶段",
            dataIndex: "current_stage_name",
            ellipsis: true,
            render: (v: string | null) => v || "—",
          },
          {
            title: "说明",
            render: (_: unknown, row: DashboardProject) => riskReason(row),
          },
        ]}
      />

      {/* —— 3. 待办 —— */}
      <Typography.Title level={4} style={{ marginTop: 32 }}>
        3. 待办问题：需要具体解决什么
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
                    {item.project_code}
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
