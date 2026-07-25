import { Button, Card, Form, Input, Typography, message } from "antd";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function LoginPage() {
  const nav = useNavigate();
  const { login } = useAuth();

  const onFinish = async (values: { username: string; password: string }) => {
    try {
      await login(values.username.trim(), values.password);
      message.success("登录成功");
      nav("/ops");
    } catch (e: unknown) {
      const err = e as { response?: { status?: number } };
      message.error(err.response?.status === 401 ? "用户名或密码错误" : "登录失败");
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#f4f6f8",
        padding: 20,
      }}
    >
      <Card
        title={
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
            <img
              src="/logo.jpg"
              alt="INNOGREEN"
              style={{ width: "100%", maxWidth: 180, height: "auto", borderRadius: 8 }}
            />
            <span style={{ fontSize: 15, fontWeight: 700, color: "#1e3a8a", whiteSpace: "nowrap" }}>
              INNOGREEN 创新绿洲
            </span>
          </div>
        }
        style={{ width: 400, maxWidth: "100%", borderRadius: 12, border: "1px solid #e5e7eb" }}
        styles={{ body: { padding: 24 } }}
      >
        <Typography.Paragraph style={{ textAlign: "center", color: "#6b7280", marginBottom: 24 }}>
          运营端登录
        </Typography.Paragraph>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input autoComplete="username" style={{ borderRadius: 8 }} />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true }]}>
            <Input.Password autoComplete="current-password" style={{ borderRadius: 8 }} />
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            block
            style={{ height: 40, borderRadius: 8, fontWeight: 600 }}
          >
            登录
          </Button>
        </Form>
        <Typography.Paragraph style={{ textAlign: "center", marginTop: 16, marginBottom: 0 }}>
          没有账号？<a onClick={() => nav("/register")}>立即注册</a>
        </Typography.Paragraph>
      </Card>
    </div>
  );
}
