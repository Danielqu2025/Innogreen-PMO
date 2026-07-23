import { Layout, Menu, Typography, Button, Tag, Space, theme } from "antd";
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
} from "@ant-design/icons";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import type { Role } from "../api/client";

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
  const { token } = theme.useToken();
  const { user, logout } = useAuth();

  const selected = resolveSelectedKey(loc.pathname);
  const settingsOpen = SETTINGS_CHILD_PREFIXES.some((p) =>
    loc.pathname.startsWith(p),
  );
  const [openKeys, setOpenKeys] = useState<string[]>(
    settingsOpen ? ["settings"] : [],
  );

  useEffect(() => {
    if (settingsOpen) {
      setOpenKeys((keys) =>
        keys.includes("settings") ? keys : [...keys, "settings"],
      );
    }
  }, [settingsOpen]);

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
      <Sider breakpoint="lg" collapsedWidth={0} width={220}>
        <div style={{ color: "#fff", padding: 16, fontWeight: 600 }}>INNOGREEN 创新绿洲</div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selected]}
          openKeys={openKeys}
          onOpenChange={setOpenKeys}
          items={items}
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
