import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from "antd";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import {
  createUser,
  listAuditLogs,
  listUsers,
  updateUser,
  type AuditLog,
  type Role,
  type User,
} from "../api/client";
import styles from "./UserManagementPage.module.css";

const ROLES: Role[] = ["admin", "operator", "viewer"];
const ROLE_LABEL: Record<Role, string> = {
  admin: "管理员",
  operator: "操作员",
  viewer: "只读",
};
const ROLE_COLOR: Record<Role, string> = {
  admin: "red",
  operator: "blue",
  viewer: "default",
};
const ACTION_LABEL: Record<string, string> = {
  CREATE: "创建",
  UPDATE: "更新",
  DELETE: "删除",
  LOGIN: "登录",
};
const RESOURCE_LABEL: Record<string, string> = {
  auth: "认证",
  users: "用户",
  projects: "企业",
  progress: "进度",
  pitfalls: "避坑",
  tasks: "任务",
  journal: "周报",
};

function errMsg(e: unknown): string {
  const err = e as { response?: { data?: { detail?: { message?: string } } } };
  return err.response?.data?.detail?.message ?? "操作失败";
}

function formatTime(v?: string | null): string {
  if (!v) return "—";
  return v.length >= 16 ? v.slice(0, 19).replace("T", " ") : v;
}

function parsePayload(raw: string | null): Record<string, unknown> | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function loginResult(row: AuditLog): { ok: boolean; label: string } {
  const p = parsePayload(row.payload);
  const ok = p?.result === "success";
  return { ok, label: ok ? "成功" : "失败" };
}

function auditDetail(row: AuditLog): string {
  const p = parsePayload(row.payload);
  if (!p) return "—";
  if (row.action === "LOGIN") {
    const parts = [loginResult(row).label];
    if (row.ip_address) parts.push(row.ip_address);
    return parts.join(" · ");
  }
  if (row.resource === "users") {
    if (row.action === "CREATE") {
      const u = typeof p.username === "string" ? p.username : "";
      const role = typeof p.role === "string" ? p.role : "";
      return [u && `用户 ${u}`, role && `角色 ${ROLE_LABEL[role as Role] ?? role}`]
        .filter(Boolean)
        .join(" · ") || "创建用户";
    }
    const after = (p.after ?? {}) as Record<string, unknown>;
    const bits: string[] = [];
    if (after.password_changed) bits.push("重置密码");
    if (typeof after.role === "string") bits.push(`角色 ${ROLE_LABEL[after.role as Role] ?? after.role}`);
    if (typeof after.is_active === "boolean") bits.push(after.is_active ? "启用" : "停用");
    if (typeof after.display_name === "string") bits.push(`显示名 ${after.display_name || "—"}`);
    return bits.join(" · ") || "更新用户";
  }
  if (row.resource_id != null) return `${RESOURCE_LABEL[row.resource] ?? row.resource} #${row.resource_id}`;
  return RESOURCE_LABEL[row.resource] ?? row.resource;
}

export default function UserManagementPage() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("active");
  const [roleFilter, setRoleFilter] = useState<Role | undefined>();
  const [statusFilter, setStatusFilter] = useState<"active" | "inactive" | undefined>("active");
  const [q, setQ] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [editUser, setEditUser] = useState<User | null>(null);
  const [pwUser, setPwUser] = useState<User | null>(null);
  const [loginLogs, setLoginLogs] = useState<AuditLog[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loginLoading, setLoginLoading] = useState(false);
  const [auditLoading, setAuditLoading] = useState(false);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();
  const [pwForm] = Form.useForm();

  const reload = useCallback(() => {
    setLoading(true);
    listUsers()
      .then(setUsers)
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, []);

  const loadLoginLogs = useCallback(() => {
    setLoginLoading(true);
    listAuditLogs({ resource: "auth", action: "LOGIN", limit: 100 })
      .then(setLoginLogs)
      .catch(() => setLoginLogs([]))
      .finally(() => setLoginLoading(false));
  }, []);

  const loadAuditLogs = useCallback(() => {
    setAuditLoading(true);
    listAuditLogs({ limit: 100 })
      .then(setAuditLogs)
      .catch(() => setAuditLogs([]))
      .finally(() => setAuditLoading(false));
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    if (activeTab === "login") loadLoginLogs();
    if (activeTab === "audit") loadAuditLogs();
  }, [activeTab, loadLoginLogs, loadAuditLogs]);

  const stats = useMemo(() => {
    const total = users.length;
    const active = users.filter((u) => u.is_active).length;
    const admins = users.filter((u) => u.role === "admin" && u.is_active).length;
    const inactive = total - active;
    const pending = 0; // 无自助注册，待审批恒为 0
    return { total, pending, active, inactive, admins };
  }, [users]);

  const filtered = useMemo(() => {
    const kw = q.trim().toLowerCase();
    return users.filter((u) => {
      if (roleFilter && u.role !== roleFilter) return false;
      if (statusFilter === "active" && !u.is_active) return false;
      if (statusFilter === "inactive" && u.is_active) return false;
      if (!kw) return true;
      return (
        u.username.toLowerCase().includes(kw) ||
        (u.display_name ?? "").toLowerCase().includes(kw)
      );
    });
  }, [users, roleFilter, statusFilter, q]);

  // 非管理员不应进入此页（菜单也不显示，这里是兜底）
  if (me && me.role !== "admin") return <Navigate to="/ops" replace />;
  if (!me) return null;
  if (error) return <Alert type="error" message={error} />;

  const onCreate = async (values: {
    username: string;
    password: string;
    display_name?: string;
    role: Role;
  }) => {
    try {
      await createUser({
        username: values.username.trim(),
        password: values.password,
        display_name: values.display_name?.trim() || undefined,
        role: values.role,
      });
      message.success("已创建");
      setCreateOpen(false);
      createForm.resetFields();
      reload();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const onEdit = async (values: { display_name?: string; role: Role }) => {
    if (!editUser) return;
    try {
      await updateUser(editUser.user_id, {
        display_name: values.display_name?.trim() || null,
        role: values.role,
      });
      message.success("已保存");
      setEditUser(null);
      editForm.resetFields();
      reload();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const onPw = async (values: { password: string }) => {
    if (!pwUser) return;
    try {
      await updateUser(pwUser.user_id, { password: values.password });
      message.success("密码已重置，请告知用户登录后立即修改");
      setPwUser(null);
      pwForm.resetFields();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const toggleActive = async (u: User) => {
    try {
      await updateUser(u.user_id, { is_active: !u.is_active });
      message.success(u.is_active ? "已停用" : "已启用");
      reload();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const openEdit = (u: User) => {
    setEditUser(u);
    editForm.setFieldsValue({
      display_name: u.display_name ?? "",
      role: u.role,
    });
  };

  const statItems = [
    { key: "total", value: stats.total, label: "用户总数" },
    { key: "pending", value: stats.pending, label: "待审批" },
    { key: "active", value: stats.active, label: "已激活" },
    { key: "inactive", value: stats.inactive, label: "已停用" },
    { key: "admins", value: stats.admins, label: "管理员" },
  ];

  const userColumns = [
    {
      title: "用户名",
      dataIndex: "username",
      render: (v: string) => <span className={styles.username}>{v}</span>,
    },
    {
      title: "显示名",
      dataIndex: "display_name",
      render: (v: string | null) => v || "—",
    },
    {
      title: "角色",
      dataIndex: "role",
      width: 100,
      render: (r: Role) => <Tag color={ROLE_COLOR[r]}>{ROLE_LABEL[r]}</Tag>,
    },
    {
      title: "状态",
      dataIndex: "is_active",
      width: 90,
      render: (a: boolean) =>
        a ? <Tag color="success">正常</Tag> : <Tag>已停用</Tag>,
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      width: 160,
      render: (v: string | null | undefined) => formatTime(v),
    },
    {
      title: "操作",
      width: 260,
      fixed: "right" as const,
      render: (_: unknown, r: User) => {
        const isSelf = r.user_id === me.user_id;
        return (
          <Space wrap size="small">
            <Button size="small" onClick={() => openEdit(r)}>
              编辑
            </Button>
            <Button
              size="small"
              onClick={() => {
                setPwUser(r);
                pwForm.resetFields();
              }}
            >
              重置密码
            </Button>
            <Popconfirm
              title={r.is_active ? "确定停用该用户吗？" : "确定启用该用户吗？"}
              okText="确定"
              cancelText="取消"
              disabled={isSelf}
              onConfirm={() => toggleActive(r)}
            >
              <Button
                size="small"
                danger={r.is_active}
                disabled={isSelf}
                type={r.is_active ? "default" : "primary"}
              >
                {r.is_active ? "停用" : "启用"}
              </Button>
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  return (
    <div>
      <div className={styles.titleRow}>
        <Typography.Title level={3}>用户管理</Typography.Title>
        <Button
          type="primary"
          onClick={() => {
            createForm.resetFields();
            setCreateOpen(true);
          }}
        >
          新增用户
        </Button>
      </div>

      <div className={styles.stats}>
        {statItems.map((s) => (
          <div key={s.key} className={styles.statCard}>
            <div className={styles.statValue}>{s.value}</div>
            <div className={styles.statLabel}>{s.label}</div>
          </div>
        ))}
      </div>

      <div className={styles.panel}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: "pending",
              label: "待审批",
              children: (
                <div className={styles.emptyHint}>
                  暂无待审批用户（本系统无自助注册，账号由管理员创建）
                </div>
              ),
            },
            {
              key: "active",
              label: "已激活用户",
              children: (
                <>
                  <Space wrap className={styles.toolbar}>
                    <Select
                      allowClear
                      placeholder="角色筛选"
                      style={{ width: 130 }}
                      value={roleFilter}
                      onChange={setRoleFilter}
                      options={ROLES.map((r) => ({ value: r, label: ROLE_LABEL[r] }))}
                    />
                    <Select
                      allowClear
                      placeholder="状态筛选"
                      style={{ width: 130 }}
                      value={statusFilter}
                      onChange={setStatusFilter}
                      options={[
                        { value: "active", label: "已激活" },
                        { value: "inactive", label: "已停用" },
                      ]}
                    />
                    <Input.Search
                      allowClear
                      placeholder="搜索用户名 / 显示名"
                      style={{ width: 220 }}
                      onSearch={setQ}
                      onChange={(e) => {
                        if (!e.target.value) setQ("");
                      }}
                    />
                  </Space>
                  <Table
                    rowKey="user_id"
                    dataSource={filtered}
                    loading={loading}
                    size="middle"
                    pagination={filtered.length > 20 ? { pageSize: 20 } : false}
                    scroll={{ x: true }}
                    columns={userColumns}
                  />
                </>
              ),
            },
            {
              key: "login",
              label: "登录记录",
              children: (
                <Table
                  rowKey="audit_id"
                  dataSource={loginLogs}
                  loading={loginLoading}
                  size="middle"
                  pagination={loginLogs.length > 20 ? { pageSize: 20 } : false}
                  locale={{ emptyText: "暂无登录记录" }}
                  columns={[
                    {
                      title: "时间",
                      dataIndex: "created_at",
                      width: 180,
                      render: (v: string) => formatTime(v),
                    },
                    {
                      title: "用户",
                      dataIndex: "actor",
                      render: (v: string) => <span className={styles.username}>{v}</span>,
                    },
                    {
                      title: "结果",
                      width: 100,
                      render: (_: unknown, row: AuditLog) => {
                        const { ok, label } = loginResult(row);
                        return <Tag color={ok ? "success" : "error"}>{label}</Tag>;
                      },
                    },
                    {
                      title: "详情",
                      render: (_: unknown, row: AuditLog) => {
                        const parts = [row.ip_address, row.user_agent?.slice(0, 60)].filter(Boolean);
                        return parts.length ? parts.join(" · ") : "—";
                      },
                    },
                  ]}
                />
              ),
            },
            {
              key: "audit",
              label: "审计日志",
              children: (
                <Table
                  rowKey="audit_id"
                  dataSource={auditLogs}
                  loading={auditLoading}
                  size="middle"
                  pagination={auditLogs.length > 20 ? { pageSize: 20 } : false}
                  locale={{ emptyText: "暂无审计日志" }}
                  scroll={{ x: true }}
                  columns={[
                    {
                      title: "时间",
                      dataIndex: "created_at",
                      width: 180,
                      render: (v: string) => formatTime(v),
                    },
                    {
                      title: "操作人",
                      dataIndex: "actor",
                      width: 120,
                      render: (v: string) => <span className={styles.username}>{v}</span>,
                    },
                    {
                      title: "动作",
                      dataIndex: "action",
                      width: 90,
                      render: (a: string) => ACTION_LABEL[a] ?? a,
                    },
                    {
                      title: "资源",
                      dataIndex: "resource",
                      width: 90,
                      render: (r: string) => RESOURCE_LABEL[r] ?? r,
                    },
                    {
                      title: "详情",
                      render: (_: unknown, row: AuditLog) => auditDetail(row),
                    },
                  ]}
                />
              ),
            },
          ]}
        />
      </div>

      <Modal
        title="新增用户"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => createForm.submit()}
        okText="创建"
        destroyOnHidden
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={onCreate}
          initialValues={{ role: "operator" }}
        >
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input autoComplete="off" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码（≥8 位）"
            rules={[{ required: true, min: 8, message: "密码至少 8 位" }]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            name="confirm"
            label="确认密码"
            dependencies={["password"]}
            rules={[
              { required: true, message: "请再次输入密码" },
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
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item name="display_name" label="显示名（可选）">
            <Input />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true }]}>
            <Select
              options={ROLES.map((x) => ({ label: ROLE_LABEL[x], value: x }))}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`编辑用户 · ${editUser?.username ?? ""}`}
        open={!!editUser}
        onCancel={() => setEditUser(null)}
        onOk={() => editForm.submit()}
        okText="保存"
        destroyOnHidden
      >
        <Form form={editForm} layout="vertical" onFinish={onEdit}>
          <Form.Item name="display_name" label="显示名">
            <Input />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true }]}>
            <Select
              options={ROLES.map((x) => ({ label: ROLE_LABEL[x], value: x }))}
              disabled={editUser?.user_id === me.user_id}
            />
          </Form.Item>
          {editUser?.user_id === me.user_id && (
            <Typography.Text type="secondary">
              不能降低自己的管理员角色
            </Typography.Text>
          )}
        </Form>
      </Modal>

      <Modal
        title={`重置密码 · ${pwUser?.username ?? ""}`}
        open={!!pwUser}
        onCancel={() => setPwUser(null)}
        onOk={() => pwForm.submit()}
        okText="重置"
        destroyOnHidden
      >
        <Form form={pwForm} layout="vertical" onFinish={onPw}>
          <Form.Item
            name="password"
            label="新密码（≥8 位）"
            rules={[{ required: true, min: 8, message: "密码至少 8 位" }]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            name="confirm"
            label="确认新密码"
            dependencies={["password"]}
            rules={[
              { required: true, message: "请再次输入新密码" },
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
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
            重置后请告知用户登录后立即修改密码。
          </Typography.Paragraph>
        </Form>
      </Modal>
    </div>
  );
}
