import { useEffect, useState } from "react";
import { Button, Card, Form, Input, Typography, message } from "antd";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { fetchSsoStatus, type SsoStatus } from "../api/client";
import logoUrl from "/logo.jpg?url";

export default function LoginPage() {
  const nav = useNavigate();
  const { login } = useAuth();
  const [sso, setSso] = useState<SsoStatus | null>(null);

  useEffect(() => {
    fetchSsoStatus().then((data) => {
      setSso(data);
      // SSO：未带 ?local=1 时直接去 Portal 登录页（与退出行为一致）
      const forceLocal = new URLSearchParams(window.location.search).has("local");
      if (data.enabled && data.portal_login_url && !forceLocal) {
        window.location.replace(data.portal_login_url);
      }
    });
  }, []);

  const onFinish = async (values: { username: string; password: string }) => {
    try {
      await login(values.username.trim(), values.password);
      message.success("登录成功");
      nav("/ops");
    } catch (e: unknown) {
      const err = e as {
        response?: { status?: number; data?: { detail?: { message?: string; code?: string } } };
      };
      const detail = err.response?.data?.detail;
      if (err.response?.status === 403 && detail?.code === "ERR_NO_APP_ACCESS") {
        message.error(detail.message || "未授权访问 PMO");
      } else {
        message.error(err.response?.status === 401 ? "用户名或密码错误" : "登录失败");
      }
    }
  };

  // SSO 跳转中：避免闪一下本地表单
  if (sso?.enabled && sso.portal_login_url && !new URLSearchParams(window.location.search).has("local")) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Typography.Text type="secondary">正在前往统一登录…</Typography.Text>
      </div>
    );
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#f4f5f7",
        padding: 20,
      }}
    >
      <Card
        title={
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
            <img
              src={logoUrl}
              alt="INNOGREEN"
              style={{ width: "100%", maxWidth: 180, height: "auto", borderRadius: 15 }}
            />
            <span style={{ fontSize: 18, fontWeight: 700, color: "#0b2b5b", whiteSpace: "nowrap" }}>
              INNOGREEN 创新绿洲
            </span>
          </div>
        }
        style={{ width: 400, maxWidth: "100%", borderRadius: 4, border: "1px solid #e5e7eb" }}
        styles={{ body: { padding: 24 } }}
      >
        <Typography.Paragraph style={{ textAlign: "center", color: "#6b7280", marginBottom: 24 }}>
          {sso?.enabled ? "统一账号登录（Portal SSO）" : "运营端登录"}
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
          {sso?.enabled ? (
            <>
              没有账号？
              {sso.portal_register_url ? (
                <a href={sso.portal_register_url}>前往 Portal 注册</a>
              ) : (
                <span>请联系管理员开通</span>
              )}
            </>
          ) : (
            <>
              没有账号？<a onClick={() => nav("/register")}>立即注册</a>
            </>
          )}
        </Typography.Paragraph>
      </Card>
    </div>
  );
}
