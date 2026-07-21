import { Layout, Menu, Typography, Button, theme } from "antd";
import {
  DashboardOutlined,
  TeamOutlined,
  NodeIndexOutlined,
  WarningOutlined,
  LogoutOutlined,
} from "@ant-design/icons";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { clearToken } from "../api/client";

const { Header, Sider, Content } = Layout;

export default function AppLayout() {
  const loc = useLocation();
  const nav = useNavigate();
  const { token } = theme.useToken();

  const selected = loc.pathname.startsWith("/ops/projects")
    ? "/ops/projects"
    : loc.pathname.startsWith("/ops/stages")
      ? "/ops/stages"
      : loc.pathname.startsWith("/ops/pitfalls")
        ? "/ops/pitfalls"
        : "/ops";

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider breakpoint="lg" collapsedWidth={0} width={220}>
        <div style={{ color: "#fff", padding: 16, fontWeight: 600 }}>
          Innogreen PMO
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selected]}
          items={[
            {
              key: "/ops",
              icon: <DashboardOutlined />,
              label: <Link to="/ops">Dashboard</Link>,
            },
            {
              key: "/ops/projects",
              icon: <TeamOutlined />,
              label: <Link to="/ops/projects">企业</Link>,
            },
            {
              key: "/ops/stages",
              icon: <NodeIndexOutlined />,
              label: <Link to="/ops/stages">阶段地图</Link>,
            },
            {
              key: "/ops/pitfalls",
              icon: <WarningOutlined />,
              label: <Link to="/ops/pitfalls">避坑指南</Link>,
            },
          ]}
        />
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
          <Typography.Text type="secondary">运营端 · Phase B 只读</Typography.Text>
          <Button
            icon={<LogoutOutlined />}
            onClick={() => {
              clearToken();
              nav("/login");
            }}
          >
            退出
          </Button>
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
