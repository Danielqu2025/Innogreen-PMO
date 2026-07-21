import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import {
  createUser,
  listUsers,
  updateUser,
  type Role,
  type User,
} from "../api/client";

const ROLES: Role[] = ["admin", "operator", "viewer"];
const ROLE_LABEL: Record<Role, string> = {
  admin: "管理员",
  operator: "操作员",
  viewer: "只读",
};

function errMsg(e: unknown): string {
  const err = e as { response?: { data?: { detail?: { message?: string } } } };
  return err.response?.data?.detail?.message ?? "操作失败";
}

export default function UserManagementPage() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [pwUser, setPwUser] = useState<User | null>(null);
  const [createForm] = Form.useForm();
  const [pwForm] = Form.useForm();

  const reload = () => {
    setLoading(true);
    listUsers()
      .then(setUsers)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    reload();
  }, []);

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

  const onPw = async (values: { password: string }) => {
    if (!pwUser) return;
    try {
      await updateUser(pwUser.user_id, { password: values.password });
      message.success("密码已重置");
      setPwUser(null);
      pwForm.resetFields();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const changeRole = async (u: User, role: Role) => {
    try {
      await updateUser(u.user_id, { role });
      message.success("角色已更新");
      reload();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const toggleActive = async (u: User) => {
    try {
      await updateUser(u.user_id, { is_active: !u.is_active });
      message.success(u.is_active ? "已禁用" : "已启用");
      reload();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  return (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          用户管理
        </Typography.Title>
        <Button type="primary" onClick={() => setCreateOpen(true)}>
          新增用户
        </Button>
      </Space>
      <Table
        rowKey="user_id"
        dataSource={users}
        loading={loading}
        size="small"
        pagination={false}
        columns={[
          { title: "用户名", dataIndex: "username" },
          { title: "显示名", dataIndex: "display_name" },
          {
            title: "角色",
            dataIndex: "role",
            width: 130,
            render: (_, r) => (
              <Select
                size="small"
                value={r.role}
                onChange={(v: Role) => changeRole(r, v)}
                options={ROLES.map((x) => ({ label: ROLE_LABEL[x], value: x }))}
                style={{ width: 100 }}
              />
            ),
          },
          {
            title: "状态",
            dataIndex: "is_active",
            width: 80,
            render: (a: boolean) =>
              a ? <Tag color="green">启用</Tag> : <Tag>禁用</Tag>,
          },
          {
            title: "操作",
            width: 220,
            render: (_: unknown, r: User) => (
              <Space>
                <Button
                  size="small"
                  onClick={() => {
                    setPwUser(r);
                    pwForm.resetFields();
                  }}
                >
                  重置密码
                </Button>
                <Button
                  size="small"
                  danger={r.is_active}
                  disabled={r.user_id === me.user_id}
                  onClick={() => toggleActive(r)}
                >
                  {r.is_active ? "禁用" : "启用"}
                </Button>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title="新增用户"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => createForm.submit()}
        okText="创建"
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={onCreate}
          initialValues={{ role: "operator" }}
        >
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码（≥8 位）"
            rules={[{ required: true, min: 8 }]}
          >
            <Input.Password />
          </Form.Item>
          <Form.Item name="display_name" label="显示名（可选）">
            <Input />
          </Form.Item>
          <Form.Item name="role" label="角色">
            <Select
              options={ROLES.map((x) => ({ label: ROLE_LABEL[x], value: x }))}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`重置密码 · ${pwUser?.username ?? ""}`}
        open={!!pwUser}
        onCancel={() => setPwUser(null)}
        onOk={() => pwForm.submit()}
        okText="重置"
      >
        <Form form={pwForm} layout="vertical" onFinish={onPw}>
          <Form.Item
            name="password"
            label="新密码（≥8 位）"
            rules={[{ required: true, min: 8 }]}
          >
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
