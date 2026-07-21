import { Button, Card, Form, Input, Typography, message } from "antd";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "../api/client";

export default function LoginPage() {
  const nav = useNavigate();

  const onFinish = async (values: { token: string }) => {
    setToken(values.token.trim());
    try {
      await api.get("/api/ops/dashboard/summary");
      message.success("登录成功");
      nav("/ops");
    } catch {
      message.error("Token 无效");
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#f5f5f5",
        padding: 16,
      }}
    >
      <Card title="Innogreen PMO 登录" style={{ width: 400, maxWidth: "100%" }}>
        <Typography.Paragraph type="secondary">
          输入与后端 <code>PMO_API_TOKEN</code> 相同的口令（开发默认见 web/.env.example）。
        </Typography.Paragraph>
        <Form layout="vertical" onFinish={onFinish} initialValues={{ token: "dev-token-change-me" }}>
          <Form.Item name="token" label="API Token" rules={[{ required: true }]}>
            <Input.Password placeholder="Bearer token" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            进入运营端
          </Button>
        </Form>
      </Card>
    </div>
  );
}
