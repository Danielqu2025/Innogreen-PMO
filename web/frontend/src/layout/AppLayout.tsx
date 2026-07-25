import { Layout, Menu, Typography, Button, Tag, Space, Modal, Form, Input } from "antd";
import {
  DashboardOutlined,
  TeamOutlined,
  NodeIndexOutlined,
  WarningOutlined,
  UserOutlined,
  UnorderedListOutlined,
  LogoutOutlined,
  SettingOutlined,
  ExportOutlined,
  ImportOutlined,
  KeyOutlined,
} from "@ant-design/icons";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { changePassword, type Role } from "../api/client";

const { Header, Sider, Content } = Layout;

const ROLE_TAG: Record<Role, { color: string; label: string }> = {
  admin: { color: "red", label: "管理员" },
  operator: { color: "blue", label: "操作员" },
  viewer: { color: "default", label: "只读" },
};

function resolveSelectedKey(pathname: string): string {
  if (pathname.startsWith("/ops/projects")) return "/ops/projects";
  if (pathname.startsWith("/ops/stages")) return "/ops/stages";
  if (pathname.startsWith("/ops/pitfalls")) return "/ops/pitfalls";
  if (pathname.startsWith("/ops/tasks")) return "/ops/tasks";
  if (pathname.startsWith("/ops/users")) return "/ops/users";
  if (pathname.startsWith("/ops/settings/export")) return "/ops/settings/export";
  if (pathname.startsWith("/ops/settings/import")) return "/ops/settings/import";
  return "/ops";
}

const SETTINGS_CHILD_PREFIXES = [
  "/ops/tasks",
  "/ops/users",
  "/ops/settings",
];

export default function AppLayout() {
  const loc = useLocation();
  const nav = useNavigate();
  const { user, logout } = useAuth();

  const selected = resolveSelectedKey(loc.pathname);
  const settingsOpen = SETTINGS_CHILD_PREFIXES.some((p) =>
    loc.pathname.startsWith(p),
  );
  const [openKeys, setOpenKeys] = useState<string[]>(
    settingsOpen ? ["settings"] : [],
  );

  // 「修改我的密码」弹窗
  const [pwOpen, setPwOpen] = useState(false);
  const [pwForm] = Form.useForm<{ current: string; next: string }>();
  const [pwSubmitting, setPwSubmitting] = useState(false);

  useEffect(() => {
    if (settingsOpen) {
      setOpenKeys((keys) =>
        keys.includes("settings") ? keys : [...keys, "settings"],
      );
    }
  }, [settingsOpen]);

  const onChangePassword = async () => {
    try {
      const v = await pwForm.validateFields();
      setPwSubmitting(true);
      await changePassword(v.current, v.next);
      pwForm.resetFields();
      setPwOpen(false);
      Modal.success({ title: "密码已修改", content: "请妥善保管新密码。" });
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: { message?: string } } } };
      Modal.error({
        title: "修改失败",
        content: err.response?.data?.detail?.message ?? "网络错误",
      });
    } finally {
      setPwSubmitting(false);
    }
  };

  const items = [
    { key: "/ops", icon: <DashboardOutlined />, label: <Link to="/ops">项目看板</Link> },
    { key: "/ops/projects", icon: <TeamOutlined />, label: <Link to="/ops/projects">企业详情</Link> },
    { key: "/ops/stages", icon: <NodeIndexOutlined />, label: <Link to="/ops/stages">阶段地图</Link> },
    { key: "/ops/pitfalls", icon: <WarningOutlined />, label: <Link to="/ops/pitfalls">避坑指南</Link> },
    ...(user?.role === "admin" || user?.role === "operator"
      ? [
          {
            key: "settings",
            icon: <SettingOutlined />,
            label: "设置",
            children: [
              ...(user.role === "admin"
                ? [
                    {
                      key: "/ops/tasks",
                      icon: <UnorderedListOutlined />,
                      label: <Link to="/ops/tasks">任务清单</Link>,
                    },
                    {
                      key: "/ops/users",
                      icon: <UserOutlined />,
                      label: <Link to="/ops/users">用户管理</Link>,
                    },
                  ]
                : []),
              {
                key: "/ops/settings/export",
                icon: <ExportOutlined />,
                label: <Link to="/ops/settings/export">数据导出</Link>,
              },
              {
                key: "/ops/settings/import",
                icon: <ImportOutlined />,
                label: <Link to="/ops/settings/import">数据导入</Link>,
              },
            ],
          },
        ]
      : []),
  ];

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        breakpoint="lg"
        collapsedWidth={0}
        width={200}
        style={{
          background: "linear-gradient(180deg, #1e3a8a, #1e40af)",
          position: "sticky",
          top: 0,
          height: "100vh",
          overflow: "auto",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 10,
            padding: "20px 16px",
            borderBottom: "1px solid rgba(255,255,255,0.1)",
          }}
        >
          <img
            src="/logo.jpg"
            alt="INNOGREEN"
            style={{ width: "100%", maxWidth: 160, height: "auto", borderRadius: 8 }}
          />
          <span style={{ color: "#fff", fontSize: 15, fontWeight: 700, whiteSpace: "nowrap" }}>
            INNOGREEN 创新绿洲
          </span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selected]}
          openKeys={openKeys}
          onOpenChange={setOpenKeys}
          items={items}
          style={{ background: "transparent", border: "none" }}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: "linear-gradient(135deg, #1e3a8a, #2563eb)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            paddingInline: 24,
            color: "#fff",
          }}
        >
          <Typography.Text style={{ color: "#fff", fontWeight: 600 }}>运营端</Typography.Text>
          <Space>
            {user && (
              <>
                <Typography.Text style={{ color: "#fff" }}>
                  {user.display_name ?? user.username}
                </Typography.Text>
                <Tag
                  color={user.role === "admin" ? "red" : user.role === "operator" ? "blue" : "default"}
                  style={{ borderRadius: 999 }}
                >
                  {ROLE_TAG[user.role].label}
                </Tag>
                <Button
                  icon={<KeyOutlined />}
                  onClick={() => {
                    pwForm.resetFields();
                    setPwOpen(true);
                  }}
                  style={{ background: "rgba(255,255,255,0.15)", border: "none", color: "#fff" }}
                >
                  修改密码
                </Button>
              </>
            )}
            <Button
              icon={<LogoutOutlined />}
              onClick={async () => {
                await logout();
                nav("/login");
              }}
              style={{ background: "rgba(255,255,255,0.15)", border: "none", color: "#fff" }}
            >
              退出
            </Button>
          </Space>
        </Header>
        <Content style={{ margin: 16, background: "#f4f6f8", minHeight: "calc(100vh - 64px)" }}>
          <div
            style={{
              background: "#fff",
              padding: 16,
              borderRadius: 12,
              minHeight: 360,
              border: "1px solid #e5e7eb",
            }}
          >
            <Outlet />
          </div>
        </Content>
      </Layout>

      <Modal
        title="修改我的密码"
        open={pwOpen}
        onCancel={() => setPwOpen(false)}
        onOk={onChangePassword}
        confirmLoading={pwSubmitting}
        okText="确认修改"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={pwForm} layout="vertical" preserve={false}>
          <Form.Item
            name="current"
            label="当前密码"
            rules={[{ required: true, message: "请输入当前密码" }]}
          >
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Form.Item
            name="next"
            label="新密码"
            rules={[
              { required: true, message: "请输入新密码" },
              { min: 8, message: "新密码至少 8 位" },
            ]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  );
}
