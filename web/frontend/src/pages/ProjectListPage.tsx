import { useEffect, useState } from "react";
import { Alert, Button, Input, Select, Space, Table, Tag, Typography } from "antd";
import { Link } from "react-router-dom";
import { api, type Project } from "../api/client";
import { useAuth } from "../auth/AuthContext";

const statusColor: Record<string, string> = {
  卡点: "error",
  进行中: "processing",
  已完成: "success",
  未开始: "default",
};

export default function ProjectListPage() {
  const { canWrite } = useAuth();
  const [rows, setRows] = useState<Project[]>([]);
  const [status, setStatus] = useState<string | undefined>();
  const [q, setQ] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params: Record<string, string> = {};
    if (status) params.status = status;
    if (q.trim()) params.q = q.trim();
    api
      .get<Project[]>("/api/ops/projects", { params })
      .then((r) => setRows(r.data))
      .catch((e) => setError(e.message));
  }, [status, q]);

  if (error) return <Alert type="error" message={error} />;

  return (
    <div>
      <Typography.Title level={3}>企业列表</Typography.Title>
      <Space wrap style={{ marginBottom: 16 }}>
        {canWrite && (
          <Link to="/ops/projects/new">
            <Button type="primary">新增企业</Button>
          </Link>
        )}
        <Select
          allowClear
          placeholder="状态筛选"
          style={{ width: 140 }}
          value={status}
          onChange={setStatus}
          options={["卡点", "进行中", "已完成", "未开始"].map((s) => ({
            value: s,
            label: s,
          }))}
        />
        <Input.Search
          placeholder="搜索 ENT / 名称"
          allowClear
          style={{ width: 220 }}
          onSearch={setQ}
        />
      </Space>
      <Table
        rowKey="project_id"
        dataSource={rows}
        pagination={false}
        scroll={{ x: true }}
        columns={[
          {
            title: "编号",
            dataIndex: "project_code",
            render: (c, r) => <Link to={`/ops/projects/${r.project_id}`}>{c}</Link>,
          },
          { title: "类型", dataIndex: "business_type" },
          { title: "楼栋", dataIndex: "building" },
          { title: "当前阶段", dataIndex: "current_stage_name" },
          {
            title: "状态",
            dataIndex: "project_status",
            render: (s: string) => <Tag color={statusColor[s] || "default"}>{s}</Tag>,
          },
          {
            title: "进度",
            dataIndex: "progress_percent",
            render: (p: number) => `${p}%`,
          },
        ]}
      />
    </div>
  );
}
