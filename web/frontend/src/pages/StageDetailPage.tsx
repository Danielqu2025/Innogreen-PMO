import { useEffect, useState } from "react";
import { Alert, List, Table, Tag, Typography } from "antd";
import { useParams } from "react-router-dom";
import { api, type Pitfall, type Stage, type Task } from "../api/client";

export default function StageDetailPage() {
  const { id } = useParams();
  const [stage, setStage] = useState<Stage | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [pitfalls, setPitfalls] = useState<Pitfall[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api.get<Stage>(`/api/ops/stages/${id}`),
      api.get<Task[]>(`/api/ops/stages/${id}/tasks`),
      api.get<Pitfall[]>(`/api/ops/stages/${id}/pitfalls`),
    ])
      .then(([s, t, p]) => {
        setStage(s.data);
        setTasks(t.data);
        setPitfalls(p.data);
      })
      .catch((e) => setError(e.message));
  }, [id]);

  if (error) return <Alert type="error" message={error} />;
  if (!stage) return <Typography.Text>加载中…</Typography.Text>;

  return (
    <div>
      <Typography.Title level={3}>
        {stage.stage_id}. {stage.stage_name}
      </Typography.Title>
      <Typography.Paragraph>{stage.description}</Typography.Paragraph>
      <Tag>{stage.critical_path}</Tag>
      <Tag>{stage.primary_owner}</Tag>
      <Tag>{stage.default_days} 天</Tag>

      <Typography.Title level={4} style={{ marginTop: 24 }}>
        任务列表
      </Typography.Title>
      <Table
        rowKey="task_id"
        dataSource={tasks}
        size="small"
        scroll={{ x: true }}
        pagination={false}
        columns={[
          { title: "编号", dataIndex: "task_code", width: 90 },
          { title: "任务", dataIndex: "task_name" },
          { title: "关键度", dataIndex: "critical_path", width: 80 },
          { title: "责任方", dataIndex: "owner", width: 120 },
        ]}
      />

      <Typography.Title level={4} style={{ marginTop: 24 }}>
        关联避坑
      </Typography.Title>
      <List
        bordered
        dataSource={pitfalls}
        locale={{ emptyText: "本阶段暂无关联避坑" }}
        renderItem={(p) => (
          <List.Item>
            <List.Item.Meta
              title={
                <>
                  <Tag color="error">{p.impact_level}</Tag>
                  {p.wrong_action}
                </>
              }
              description={`合规：${p.right_action}`}
            />
          </List.Item>
        )}
      />
    </div>
  );
}
