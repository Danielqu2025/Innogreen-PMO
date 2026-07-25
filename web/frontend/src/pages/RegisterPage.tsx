import { Button, Card, Form, Input, Typography, message } from "antd";
import { useNavigate } from "react-router-dom";
import { register as apiRegister } from "../api/client";

export default function RegisterPage() {
  const nav = useNavigate();

  const onFinish = async (values: {
    username: string;
    password: string;
    display_name?: string;
  }) => {
    try {
      await apiRegister(
        values.username.trim(),
        values.password,
        values.display_name,
      );
      message.success("注册成功，已自动登录");
      nav("/ops");
    } catch (e: unknown) {
      const err = e as { response?: { status?: number; data?: { detail?: { message?: string } } } };
      const status = err.response?.status;
      const errMsg = err.response?.data?.detail?.message;

      if (status === 409 && errMsg) {
        message.error(errMsg); // "用户名已存在"
      } else if (status === 422 && errMsg) {
        message.error(errMsg); // 验证错误
      } else {
        message.error("注册失败，请重试");
      }
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
        <Typography.Paragraph type="secondary">
          注册后默认为「访客」角色（只读）。如需写入权限，请联系管理员提升。
        </Typography.Paragraph>
        <Typography.Paragraph type="secondary" style={{ fontSize: 12, color: "#888" }}>
          <b>注意：</b>用户名至少 2 个字符，密码至少 8 个字符且不能太简单。
        </Typography.Paragraph>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item
            name="username"
            label="用户名"
            rules={[
              { required: true, message: "请输入用户名" },
              { min: 2, message: "用户名至少 2 个字符" },
            ]}
          >
            <Input autoComplete="username" placeholder="用于登录" />
          </Form.Item>
          <Form.Item name="display_name" label="显示名称（可选）">
            <Input placeholder="如：张三" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[
              { required: true, message: "请输入密码" },
              { min: 8, message: "密码至少 8 个字符" },
            ]}
          >
            <Input.Password autoComplete="new-password" placeholder="至少 8 个字符" />
          </Form.Item>
          <Form.Item
            name="confirm"
            label="确认密码"
            dependencies={["password"]}
            rules={[
              { required: true, message: "请确认密码" },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue("password") === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error("两次密码不一致"));
                },
              }),
            ]}
          >
            <Input.Password autoComplete="new-password" placeholder="再次输入密码" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            注册
          </Button>
        </Form>
        <Typography.Paragraph style={{ textAlign: "center", marginTop: 16, marginBottom: 0 }}>
          已有账号？{" "}
          <a onClick={() => nav("/login")}>立即登录</a>
        </Typography.Paragraph>
      </Card>
    </div>
  );
}
