import { useEffect, useState } from "react";
import { Alert, Col, List, Row, Statistic, Tag, Typography } from "antd";
import { Link } from "react-router-dom";
import { api, type DashboardSummary } from "../api/client";

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

  return (
    <div>
      <Typography.Title level={3}>运营 Dashboard</Typography.Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <Statistic title="企业总数" value={data.total_projects} />
        </Col>
        {Object.entries(data.by_status).map(([k, v]) => (
          <Col xs={12} sm={8} key={k}>
            <Statistic title={k} value={v} />
          </Col>
        ))}
      </Row>

      <Typography.Title level={4} style={{ marginTop: 24 }}>
        阶段分布
      </Typography.Title>
      <List
        size="small"
        dataSource={Object.entries(data.by_stage)}
        renderItem={([name, count]) => (
          <List.Item>
            <span>{name}</span>
            <Tag>{count}</Tag>
          </List.Item>
        )}
      />

      <Typography.Title level={4} style={{ marginTop: 24 }}>
        卡点提醒
      </Typography.Title>
      <List
        bordered
        dataSource={data.blockers}
        locale={{ emptyText: "暂无卡点" }}
        renderItem={(b) => (
          <List.Item>
            <List.Item.Meta
              title={
                <Link to={`/ops/projects/${b.project_id}`}>
                  {b.project_code} · {b.task_code} {b.task}
                </Link>
              }
              description={b.note}
            />
            <Tag color="error">{b.project_status}</Tag>
          </List.Item>
        )}
      />
    </div>
  );
}
