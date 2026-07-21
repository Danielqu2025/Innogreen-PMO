import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Descriptions,
  Space,
  Steps,
  Table,
  Tag,
  Timeline,
  Typography,
} from "antd";
import { Link, useParams } from "react-router-dom";
import {
  api,
  listProjectJournal,
  type CriticalPath,
  type JournalEntry,
  type Progress,
  type Project,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";

const statusColor: Record<string, string> = {
  卡点: "error",
  进行中: "processing",
  已完成: "success",
  待开始: "default",
  已跳过: "warning",
};

function stepStatus(s: string): "wait" | "process" | "finish" | "error" {
  if (s === "卡点") return "error";
  if (s === "已完成") return "finish";
  if (s === "进行中") return "process";
  return "wait";
}

export default function ProjectDetailPage() {
  const { id } = useParams();
  const { canWrite } = useAuth();
  const [project, setProject] = useState<Project | null>(null);
  const [progress, setProgress] = useState<Progress[]>([]);
  const [cp, setCp] = useState<CriticalPath | null>(null);
  const [journals, setJournals] = useState<JournalEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    const pid = Number(id);
    Promise.all([
      api.get<Project>(`/api/ops/projects/${id}`),
      api.get<Progress[]>(`/api/ops/projects/${id}/progress`),
      api.get<CriticalPath>(`/api/ops/projects/${id}/critical-path`),
      listProjectJournal(pid, { limit: 40 }),
    ])
      .then(([p, pr, c, j]) => {
        setProject(p.data);
        setProgress(pr.data);
        setCp(c.data);
        setJournals(j);
      })
      .catch((e) => setError(e.message));
  }, [id]);

  if (error) return <Alert type="error" message={error} />;
  if (!project) return <Typography.Text>加载中…</Typography.Text>;

  const highlight = cp?.nodes.filter((n) =>
    ["卡点", "进行中", "已完成"].includes(n.status),
  );

  return (
    <div>
      <Space style={{ marginBottom: 8 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          {project.project_code}
        </Typography.Title>
        {canWrite && (
          <Link to={`/ops/projects/${id}/edit`}>
            <Button size="small">编辑</Button>
          </Link>
        )}
      </Space>
      <Descriptions bordered size="small" column={{ xs: 1, sm: 2 }}>
        <Descriptions.Item label="状态">
          <Tag color={statusColor[project.project_status]}>{project.project_status}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="进度">{project.progress_percent}%</Descriptions.Item>
        <Descriptions.Item label="类型">{project.business_type}</Descriptions.Item>
        <Descriptions.Item label="楼栋">{project.building}</Descriptions.Item>
        <Descriptions.Item label="当前阶段" span={2}>
          {project.current_stage_name}
        </Descriptions.Item>
        <Descriptions.Item label="备注" span={2}>
          {project.notes}
        </Descriptions.Item>
      </Descriptions>

      <Typography.Title level={4} style={{ marginTop: 24 }}>
        关键路径（关键任务）
      </Typography.Title>
      {highlight && highlight.length > 0 ? (
        <Steps
          direction="vertical"
          size="small"
          items={highlight.map((n) => ({
            title: `${n.task_code ?? ""} ${n.task_name}`,
            description: n.blocker_note || n.stage_name,
            status: stepStatus(n.status),
          }))}
        />
      ) : (
        <Typography.Text type="secondary">暂无关键任务进度</Typography.Text>
      )}

      <Typography.Title level={4} style={{ marginTop: 24 }}>
        任务进度
      </Typography.Title>
      <Table
        rowKey="progress_id"
        dataSource={progress}
        size="small"
        scroll={{ x: true }}
        pagination={{ pageSize: 20 }}
        columns={[
          { title: "编号", dataIndex: "task_code", width: 90 },
          { title: "任务", dataIndex: "task_name" },
          {
            title: "状态",
            dataIndex: "status",
            width: 100,
            render: (s: string) => <Tag color={statusColor[s] || "default"}>{s}</Tag>,
          },
          {
            title: "计划起止",
            width: 160,
            render: (_: unknown, row: Progress) => {
              const a = row.planned_start?.slice(0, 10) ?? "";
              const b = row.planned_end?.slice(0, 10) ?? "";
              return a || b ? `${a || "—"} ~ ${b || "—"}` : "—";
            },
          },
          {
            title: "实际完成",
            dataIndex: "completed_at",
            width: 110,
            render: (v: string | null | undefined) => v?.slice(0, 10) || "—",
          },
          { title: "第三方", dataIndex: "vendor", width: 140, ellipsis: true },
          { title: "负责人", dataIndex: "assigned_to", width: 100 },
          { title: "卡点说明", dataIndex: "blocker_note", ellipsis: true },
          ...(canWrite
            ? [
                {
                  title: "操作",
                  width: 80,
                  render: (_: unknown, row: Progress) => (
                    <Link to={`/ops/projects/${id}/tasks/${row.task_id}`}>
                      <Button type="link" size="small">
                        更新
                      </Button>
                    </Link>
                  ),
                },
              ]
            : []),
        ]}
      />

      <Typography.Title level={4} style={{ marginTop: 24 }}>
        周进展（最近 {journals.length} 条）
      </Typography.Title>
      {journals.length === 0 ? (
        <Typography.Text type="secondary">暂无周记（导入或任务页可追加）</Typography.Text>
      ) : (
        <Timeline
          items={journals.map((j) => ({
            children: (
              <div>
                <Typography.Text strong>
                  {j.week_start}
                  {j.week_label ? ` · ${j.week_label}` : ""}
                </Typography.Text>
                <div>
                  <Typography.Text type="secondary">
                    {j.task_code ? `${j.task_code} ${j.task_name ?? ""}` : "项目级"}
                    {j.source === "excel_import" ? " · Excel导入" : ""}
                    {j.actor ? ` · ${j.actor}` : ""}
                  </Typography.Text>
                </div>
                <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}>
                  {j.note}
                </Typography.Paragraph>
              </div>
            ),
          }))}
        />
      )}
    </div>
  );
}
