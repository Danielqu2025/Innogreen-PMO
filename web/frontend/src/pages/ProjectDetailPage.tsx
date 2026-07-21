import { useEffect, useState } from "react";
import { Alert, Descriptions, Steps, Table, Tag, Typography } from "antd";
import { useParams } from "react-router-dom";
import {
  api,
  type CriticalPath,
  type Progress,
  type Project,
} from "../api/client";

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
  const [project, setProject] = useState<Project | null>(null);
  const [progress, setProgress] = useState<Progress[]>([]);
  const [cp, setCp] = useState<CriticalPath | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api.get<Project>(`/api/ops/projects/${id}`),
      api.get<Progress[]>(`/api/ops/projects/${id}/progress`),
      api.get<CriticalPath>(`/api/ops/projects/${id}/critical-path`),
    ])
      .then(([p, pr, c]) => {
        setProject(p.data);
        setProgress(pr.data);
        setCp(c.data);
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
      <Typography.Title level={3}>{project.project_code}</Typography.Title>
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
          { title: "负责人", dataIndex: "assigned_to", width: 100 },
          { title: "卡点说明", dataIndex: "blocker_note" },
        ]}
      />
    </div>
  );
}
