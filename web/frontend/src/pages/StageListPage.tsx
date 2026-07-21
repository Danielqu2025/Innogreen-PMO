import { useEffect, useState } from "react";
import { Alert, Card, Col, Row, Tag, Typography } from "antd";
import { Link } from "react-router-dom";
import { api, type Stage } from "../api/client";

export default function StageListPage() {
  const [stages, setStages] = useState<Stage[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Stage[]>("/api/ops/stages")
      .then((r) => setStages(r.data))
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <Alert type="error" message={error} />;

  return (
    <div>
      <Typography.Title level={3}>阶段地图（8）</Typography.Title>
      <Row gutter={[12, 12]}>
        {stages.map((s) => (
          <Col xs={24} sm={12} lg={8} key={s.stage_id}>
            <Link to={`/ops/stages/${s.stage_id}`}>
              <Card hoverable size="small" title={`${s.stage_id}. ${s.stage_name}`}>
                <div>
                  <Tag>{s.critical_path}</Tag>
                  <Tag>{s.task_count} 任务</Tag>
                </div>
                <Typography.Paragraph type="secondary" ellipsis={{ rows: 2 }}>
                  {s.description || s.primary_owner}
                </Typography.Paragraph>
              </Card>
            </Link>
          </Col>
        ))}
      </Row>
    </div>
  );
}
