import { useEffect, useState } from "react";
import { Alert, Input, Select, Space, Table, Tag, Typography } from "antd";
import { api, type Pitfall } from "../api/client";

export default function PitfallListPage() {
  const [rows, setRows] = useState<Pitfall[]>([]);
  const [impact, setImpact] = useState<string | undefined>();
  const [q, setQ] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params: Record<string, string> = {};
    if (impact) params.impact = impact;
    if (q.trim()) params.q = q.trim();
    api
      .get<Pitfall[]>("/api/ops/pitfalls", { params })
      .then((r) => setRows(r.data))
      .catch((e) => setError(e.message));
  }, [impact, q]);

  if (error) return <Alert type="error" message={error} />;

  return (
    <div>
      <Typography.Title level={3}>避坑指南</Typography.Title>
      <Space wrap style={{ marginBottom: 16 }}>
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
            title: "影响",
            dataIndex: "impact_level",
            width: 80,
            render: (v: string) => (
              <Tag color={v === "极高" || v === "高" ? "error" : "warning"}>{v}</Tag>
            ),
          },
          { title: "阶段", dataIndex: "stage_ref", width: 160 },
          { title: "错误做法", dataIndex: "wrong_action" },
          { title: "合规做法", dataIndex: "right_action" },
          { title: "依据", dataIndex: "standard_ref" },
        ]}
      />
    </div>
  );
}
