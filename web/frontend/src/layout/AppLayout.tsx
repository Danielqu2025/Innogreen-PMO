import { Layout, Modal, Form, Input, message } from "antd";
import { Link, Outlet, useLocation } from "react-router-dom";
import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";
import { api, changePassword, type Role } from "../api/client";
import logoUrl from "/logo.jpg?url";
import { ShellHomeIcon, ShellKeyIcon, ShellLogoutIcon } from "./ShellTopIcons";
import {
  SideIconCaret,
  SideIconDashboard,
  SideIconExport,
  SideIconImport,
  SideIconList,
  SideIconSettings,
  SideIconStages,
  SideIconTeam,
  SideIconUser,
  SideIconWarning,
} from "./ShellSideIcons";
import "./shell-top-actions.css";
import "./shell-sidebar.css";
import "./AppLayout.css";

const { Header } = Layout;

const ROLE_LABEL: Record<Role, string> = {
  admin: "管理员",
  operator: "操作员",
  viewer: "只读",
};

function resolveSelectedKey(pathname: string): string {
  if (pathname.startsWith("/ops/projects")) return "/ops/projects";
  if (pathname.startsWith("/ops/stages")) return "/ops/stages";
  if (pathname.startsWith("/ops/pitfalls")) return "/ops/pitfalls";
  if (pathname.startsWith("/ops/tasks")) return "/ops/tasks";
  if (pathname.startsWith("/ops/users")) return "/ops/users";
  if (pathname.startsWith("/ops/settings/export")) return "/ops/settings/export";
  if (pathname.startsWith("/ops/settings/import")) return "/ops/settings/import";
  if (pathname.startsWith("/ops/settings/alerts")) return "/ops/settings/alerts";
  return "/ops";
}

const SETTINGS_CHILD_PREFIXES = [
  "/ops/tasks",
  "/ops/users",
  "/ops/settings",
];

function SideLink({
  to,
  href,
  icon,
  title,
  sub,
  active,
  child,
  onClick,
}: {
  to?: string;
  href?: string;
  icon: ReactNode;
  title: string;
  sub?: string;
  active?: boolean;
  child?: boolean;
  onClick?: () => void;
}) {
  const cls = [
    "shell-side-link",
    active ? "is-active" : "",
    child ? "is-child" : "",
  ]
    .filter(Boolean)
    .join(" ");
  const body = (
    <>
      {icon}
      <span className="shell-side-body">
        <span className="shell-side-title">{title}</span>
        {sub ? <em>{sub}</em> : null}
      </span>
    </>
  );
  if (href) {
    return (
      <a className={cls} href={href} target="_blank" rel="noreferrer" onClick={onClick}>
        {body}
      </a>
    );
  }
  return (
    <Link className={cls} to={to || "/ops"} onClick={onClick}>
      {body}
    </Link>
  );
}

export default function AppLayout() {
  const loc = useLocation();
  const { user, logout } = useAuth();

  const selected = resolveSelectedKey(loc.pathname);
  const settingsOpen = SETTINGS_CHILD_PREFIXES.some((p) =>
    loc.pathname.startsWith(p),
  );
  const [settingsExpanded, setSettingsExpanded] = useState(settingsOpen);
  const [ssoEnabled, setSsoEnabled] = useState(false);
  const [portalWebUrl, setPortalWebUrl] = useState<string | null>(null);

  const [pwOpen, setPwOpen] = useState(false);
  const [pwForm] = Form.useForm<{ current: string; next: string }>();
  const [pwSubmitting, setPwSubmitting] = useState(false);
  const [navOpen, setNavOpen] = useState(false);

  useEffect(() => {
    api
      .get<{ enabled: boolean; portal_web_url: string | null }>("/api/auth/sso-status")
      .then((r) => {
        setSsoEnabled(!!r.data.enabled);
        setPortalWebUrl(r.data.portal_web_url);
      })
      .catch(() => {
        setSsoEnabled(false);
        setPortalWebUrl(null);
      });
  }, []);

  useEffect(() => {
    if (settingsOpen) setSettingsExpanded(true);
  }, [settingsOpen]);

  useEffect(() => {
    setNavOpen(false);
  }, [loc.pathname]);

  useEffect(() => {
    document.body.classList.toggle("shell-nav-open", navOpen);
    return () => document.body.classList.remove("shell-nav-open");
  }, [navOpen]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setNavOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

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

  const portalAdminUrl = portalWebUrl
    ? `${portalWebUrl.replace(/\/$/, "")}/admin`
    : null;

  const canWrite = user?.role === "admin" || user?.role === "operator";

  return (
    <Layout className="pmo-shell">
      <div
        className="shell-sidebar-backdrop"
        hidden={!navOpen}
        onClick={() => setNavOpen(false)}
        aria-hidden={!navOpen}
      />
      <Header className="pmo-topbar">
        <button
          type="button"
          className="shell-nav-toggle"
          aria-label={navOpen ? "关闭菜单" : "打开菜单"}
          aria-expanded={navOpen}
          aria-controls="pmo-sidebar"
          onClick={() => setNavOpen((v) => !v)}
        >
          <span className="shell-nav-toggle-bar" />
          <span className="shell-nav-toggle-bar" />
          <span className="shell-nav-toggle-bar" />
        </button>
        <div className="pmo-brand">
          <span className="pmo-brand-logo-wrap">
            <img src={logoUrl} alt="INNOGREEN" />
          </span>
          <div className="pmo-brand-text">
            <strong>INNOGREEN 创新绿洲</strong>
            <span>PMO · 项目管理办公室</span>
          </div>
        </div>
        <nav className="shell-top-actions" aria-label="账户操作">
          {user && ssoEnabled && portalWebUrl && (
            <button
              type="button"
              className="shell-top-btn"
              onClick={() => {
                window.location.href = portalWebUrl.replace(/\/$/, "");
              }}
            >
              <ShellHomeIcon />
              <span>返回门户</span>
            </button>
          )}
          {user && (
            <button
              type="button"
              className="shell-top-btn"
              onClick={() => {
                if (ssoEnabled) {
                  const url = portalAdminUrl || portalWebUrl;
                  if (url) window.open(url, "_blank");
                  else message.info("请在 Portal 管理账号");
                  return;
                }
                pwForm.resetFields();
                setPwOpen(true);
              }}
            >
              <ShellKeyIcon />
              <span>
                {ssoEnabled
                  ? user.role === "admin"
                    ? "账号管理"
                    : "Portal 账号"
                  : "修改密码"}
              </span>
            </button>
          )}
          <button
            type="button"
            className="shell-top-btn"
            onClick={async () => {
              await logout();
            }}
          >
            <ShellLogoutIcon />
            <span>退出</span>
          </button>
        </nav>
      </Header>

      {/* 与 Portal/qcc 同结构：aside.shell-sidebar（不用 Ant Sider，避免 wrapper 导致账号卡错位） */}
      <div className="pmo-body">
        <aside className="shell-sidebar" id="pmo-sidebar">
          <div className="shell-sidebar-brand">菜单</div>
          <div className="shell-sidebar-top">
            {user && (
              <div className="shell-user-box">
                <div className="shell-user-box-name">
                  {user.display_name ?? user.username}
                </div>
                <div className="shell-user-box-meta">
                  {ROLE_LABEL[user.role]} · @{user.username}
                </div>
              </div>
            )}
            <div className="shell-sidebar-label">快捷入口</div>
            <ul
              className="shell-side-list"
              onClick={(e) => {
                const t = e.target as HTMLElement;
                if (t.closest("a.shell-side-link")) setNavOpen(false);
              }}
            >
              <li>
                <SideLink
                  to="/ops"
                  icon={<SideIconDashboard />}
                  title="项目看板"
                  active={selected === "/ops"}
                />
              </li>
              <li>
                <SideLink
                  to="/ops/projects"
                  icon={<SideIconTeam />}
                  title="企业详情"
                  active={selected === "/ops/projects"}
                />
              </li>
              <li>
                <SideLink
                  to="/ops/stages"
                  icon={<SideIconStages />}
                  title="阶段地图"
                  active={selected === "/ops/stages"}
                />
              </li>
              <li>
                <SideLink
                  to="/ops/pitfalls"
                  icon={<SideIconWarning />}
                  title="避坑指南"
                  active={selected === "/ops/pitfalls"}
                />
              </li>
              {canWrite && (
                <li>
                  <button
                    type="button"
                    className={`shell-side-link shell-side-group-toggle${settingsExpanded ? " is-open" : ""}`}
                    onClick={() => setSettingsExpanded((v) => !v)}
                  >
                    <SideIconSettings />
                    <span className="shell-side-body">
                      <span className="shell-side-title">设置</span>
                    </span>
                    <SideIconCaret />
                  </button>
                  <div
                    className={`shell-side-group-children${settingsExpanded ? " is-open" : ""}`}
                  >
                    {user?.role === "admin" && (
                      <>
                        <SideLink
                          to="/ops/tasks"
                          icon={<SideIconList />}
                          title="任务清单"
                          active={selected === "/ops/tasks"}
                          child
                        />
                        <SideLink
                          to="/ops/settings/alerts"
                          icon={<SideIconWarning />}
                          title="预警机制"
                          active={selected === "/ops/settings/alerts"}
                          child
                        />
                        {ssoEnabled ? (
                          portalAdminUrl ? (
                            <SideLink
                              href={portalAdminUrl}
                              icon={<SideIconUser />}
                              title="账号管理"
                              child
                            />
                          ) : null
                        ) : (
                          <SideLink
                            to="/ops/users"
                            icon={<SideIconUser />}
                            title="用户管理"
                            active={selected === "/ops/users"}
                            child
                          />
                        )}
                      </>
                    )}
                    <SideLink
                      to="/ops/settings/export"
                      icon={<SideIconExport />}
                      title="数据导出"
                      active={selected === "/ops/settings/export"}
                      child
                    />
                    <SideLink
                      to="/ops/settings/import"
                      icon={<SideIconImport />}
                      title="数据导入"
                      active={selected === "/ops/settings/import"}
                      child
                    />
                  </div>
                </li>
              )}
            </ul>
          </div>
          <div className="shell-sidebar-bottom">
            <div className="shell-notice">
              <strong>统一身份</strong>
              一次登录，访问你被授权的全部 INNOGREEN 应用。权限由门户管理员统一配置。
            </div>
            <div className="shell-side-foot">
              上海国际化工新材料创新中心
              <br />
              Shanghai International Chemical New Materials Innovation Center
            </div>
          </div>
        </aside>
        <main className="pmo-content">
          <div className="pmo-panel">
            <Outlet />
          </div>
        </main>
      </div>

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
