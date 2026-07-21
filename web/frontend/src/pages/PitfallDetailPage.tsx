import { useEffect, useState } from "react";
import { Alert, Descriptions, Tag, Typography } from "antd";
import { Link, useParams } from "react-router-dom";
import { api, type PitfallDetail } from "../api/client";

export default function PitfallDetailPage() {
  const { id } = useParams();
  const [pitfall, setPitfall] = useState<PitfallDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api
      .get<PitfallDetail>(`/api/ops/pitfalls/${id}`)
      .then((r) => setPitfall(r.data))
      .catch((e) => setError(e.message));
  }, [id]);

  if (error) return <Alert type="error" message={error} />;
  if (!pitfall) return <Typography.Text>加载中…</Typography.Text>;

  const impactColor =
    pitfall.impact_level === "极高" || pitfall.impact_level === "高" ? "error" : "warning";

  return (
    <div>
      <Typography.Title level={3}>避坑详情 #{pitfall.pitfall_id}</Typography.Title>
      <Descriptions bordered size="small" column={{ xs: 1, sm: 2 }}>
        <Descriptions.Item label="阶段" span={2}>
          {pitfall.stage_ref}
        </Descriptions.Item>
        <Descriptions.Item label="影响等级">
          <Tag color={impactColor}>{pitfall.impact_level}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="错误指数">{pitfall.error_index}</Descriptions.Item>
        <Descriptions.Item label="错误做法" span={2}>
          {pitfall.wrong_action}
        </Descriptions.Item>
        <Descriptions.Item label="合规做法" span={2}>
          {pitfall.right_action}
        </Descriptions.Item>
        <Descriptions.Item label="依据/规范" span={2}>
          {pitfall.standard_ref || "—"}
        </Descriptions.Item>
        <Descriptions.Item label="触发条件" span={2}>
          {pitfall.trigger_condition || "—"}
        </Descriptions.Item>
        <Descriptions.Item label="补救建议" span={2}>
          {pitfall.remediation || "—"}
        </Descriptions.Item>
        <Descriptions.Item label="来源">{pitfall.source}</Descriptions.Item>
        <Descriptions.Item label="已验证">
          {pitfall.verified ? "是" : "否"}
        </Descriptions.Item>
        <Descriptions.Item label="备注" span={2}>
          {pitfall.notes || "—"}
        </Descriptions.Item>
      </Descriptions>
      <Typography.Paragraph style={{ marginTop: 16 }}>
        <Link to="/ops/pitfalls">← 返回列表</Link>
      </Typography.Paragraph>
    </div>
  );
}
