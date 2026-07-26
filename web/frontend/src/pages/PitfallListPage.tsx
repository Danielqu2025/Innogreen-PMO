import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Cascader,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import { Link } from "react-router-dom";
import { api, type Pitfall, type Stage, type Task } from "../api/client";
import { useAuth } from "../auth/AuthContext";

function taskLevel(code: string | null | undefined): number {
  if (!code) return 0;
  return code.split(".").length;
}

export default function PitfallListPage() {
  const { canWrite } = useAuth();
  const [rows, setRows] = useState<Pitfall[]>([]);
  const [stages, setStages] = useState<Stage[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [stageTaskPath, setStageTaskPath] = useState<string[]>([]);
  const [impact, setImpact] = useState<string | undefined>();
  const [q, setQ] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<Stage[]>("/api/ops/stages").then((r) => r.data),
      api.get<Task[]>("/api/ops/tasks").then((r) => r.data),
    ])
      .then(([s, t]) => {
        setStages(s);
        setTasks(t);
      })
      .catch((e) => setError(e.message));
  }, []);

  const taskNameByCode = useMemo(() => {
    const map = new Map<string, string>();
    for (const t of tasks) {
      if (t.task_code) map.set(t.task_code, t.task_name);
    }
    return map;
  }, [tasks]);

  const stageTaskOptions = useMemo(() => {
    return stages.map((s) => {
      const children = tasks
        .filter((t) => t.stage_id === s.stage_id && taskLevel(t.task_code) >= 2)
        .map((t) => ({
          label: `${t.task_code} · ${t.task_name}`,
          value: t.task_code as string,
        }))
        .sort((a, b) =>
          a.value.localeCompare(b.value, undefined, { numeric: true }),
        );
      return {
        label: s.stage_name,
        value: s.stage_name,
        children: children.length ? children : undefined,
      };
    });
  }, [stages, tasks]);

  useEffect(() => {
    const params: Record<string, string> = {};
    if (stageTaskPath[0]) params.stage = stageTaskPath[0];
    if (stageTaskPath[1]) params.task = stageTaskPath[1];
    if (impact) params.impact = impact;
    if (q.trim()) params.q = q.trim();
    api
      .get<Pitfall[]>("/api/ops/pitfalls", { params })
      .then((r) => setRows(r.data))
      .catch((e) => setError(e.message));
  }, [stageTaskPath, impact, q]);

  if (error) return <Alert type="error" message={error} />;

  return (
    <div>
      <Typography.Title level={3}>避坑指南</Typography.Title>
      <Space wrap style={{ marginBottom: 16 }}>
        {canWrite && (
          <Link to="/ops/pitfalls/new">
            <Button type="primary">录入避坑</Button>
          </Link>
        )}
        <Cascader
          allowClear
          changeOnSelect
          showSearch
          placeholder="阶段 / 任务"
          style={{ width: 280 }}
          options={stageTaskOptions}
          value={stageTaskPath.length ? stageTaskPath : undefined}
          onChange={(v) => setStageTaskPath((v as string[] | undefined) ?? [])}
        />
        <Select
          allowClear
          placeholder="影响等级"
          style={{ width: 140 }}
          value={impact}
          onChange={setImpact}
          options={["极高", "高", "中", "低"].map((s) => ({ value: s, label: s }))}
        />
        <Input.Search
          placeholder="关键词"
          allowClear
          style={{ width: 220 }}
          onSearch={setQ}
        />
      </Space>
      <Table
        rowKey="pitfall_id"
        dataSource={rows}
        scroll={{ x: true }}
        pagination={false}
        columns={[
          {
            title: "ID",
            dataIndex: "pitfall_id",
            width: 60,
            render: (id: number) => <Link to={`/ops/pitfalls/${id}`}>{id}</Link>,
          },
          {
            title: "影响",
            dataIndex: "impact_level",
            width: 80,
            render: (v: string) => (
              <Tag color={v === "极高" || v === "高" ? "error" : "warning"}>{v}</Tag>
            ),
          },
          { title: "阶段", dataIndex: "stage_ref", width: 160 },
          {
            title: "任务",
            dataIndex: "task_ref",
            width: 200,
            render: (code: string | null) => {
              if (!code) return "—";
              const name = taskNameByCode.get(code);
              return name ? `${code} · ${name}` : code;
            },
          },
          { title: "错误做法", dataIndex: "wrong_action" },
          { title: "合规做法", dataIndex: "right_action" },
          { title: "依据", dataIndex: "standard_ref" },
        ]}
      />
    </div>
  );
}
