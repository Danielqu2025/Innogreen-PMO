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
        background: "#f5f5f5",
        padding: 16,
      }}
    >
      <Card title="Innogreen PMO 登录" style={{ width: 400, maxWidth: "100%" }}>
        <Typography.Paragraph type="secondary">
          使用管理员分配的账号密码登录。
        </Typography.Paragraph>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input autoComplete="username" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            进入运营端
          </Button>
        </Form>
      </Card>
    </div>
  );
}
