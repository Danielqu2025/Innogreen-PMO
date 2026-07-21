import { Layout, Menu, Typography, Button, Tag, Space, theme } from "antd";
import {
  DashboardOutlined,
  TeamOutlined,
  NodeIndexOutlined,
  WarningOutlined,
  UserOutlined,
  UnorderedListOutlined,
  LogoutOutlined,
} from "@ant-design/icons";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import type { Role } from "../api/client";

const { Header, Sider, Content } = Layout;

const ROLE_TAG: Record<Role, { color: string; label: string }> = {
  admin: { color: "red", label: "管理员" },
  operator: { color: "blue", label: "操作员" },
  viewer: { color: "default", label: "只读" },
};

export default function AppLayout() {
  const loc = useLocation();
  const nav = useNavigate();
  const { token } = theme.useToken();
  const { user, logout } = useAuth();

  const selected = loc.pathname.startsWith("/ops/projects")
    ? "/ops/projects"
    : loc.pathname.startsWith("/ops/stages")
      ? "/ops/stages"
      : loc.pathname.startsWith("/ops/pitfalls")
        ? "/ops/pitfalls"
        : loc.pathname.startsWith("/ops/tasks")
          ? "/ops/tasks"
          : loc.pathname.startsWith("/ops/users")
            ? "/ops/users"
            : "/ops";

  const items = [
    { key: "/ops", icon: <DashboardOutlined />, label: <Link to="/ops">Dashboard</Link> },
    { key: "/ops/projects", icon: <TeamOutlined />, label: <Link to="/ops/projects">企业</Link> },
    { key: "/ops/stages", icon: <NodeIndexOutlined />, label: <Link to="/ops/stages">阶段地图</Link> },
    { key: "/ops/pitfalls", icon: <WarningOutlined />, label: <Link to="/ops/pitfalls">避坑指南</Link> },
    ...(user?.role === "admin"
      ? [
          {
            key: "/ops/tasks",
            icon: <UnorderedListOutlined />,
            label: <Link to="/ops/tasks">任务清单</Link>,
          },
          { key: "/ops/users", icon: <UserOutlined />, label: <Link to="/ops/users">用户管理</Link> },
        ]
      : []),
  ];

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider breakpoint="lg" collapsedWidth={0} width={220}>
        <div style={{ color: "#fff", padding: 16, fontWeight: 600 }}>Innogreen PMO</div>
        <Menu theme="dark" mode="inline" selectedKeys={[selected]} items={items} />
      </Sider>
      <Layout>
        <Header
          style={{
            background: token.colorBgContainer,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            paddingInline: 24,
          }}
        >
          <Typography.Text type="secondary">运营端</Typography.Text>
          <Space>
            {user && (
              <>
                <Typography.Text>{user.display_name ?? user.username}</Typography.Text>
                <Tag color={ROLE_TAG[user.role].color}>{ROLE_TAG[user.role].label}</Tag>
              </>
            )}
            <Button
              icon={<LogoutOutlined />}
              onClick={async () => {
                await logout();
                nav("/login");
              }}
            >
              退出
            </Button>
          </Space>
        </Header>
        <Content style={{ margin: 16 }}>
          <div
            style={{
              background: token.colorBgContainer,
              padding: 16,
              borderRadius: 8,
              minHeight: 360,
            }}
          >
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}
