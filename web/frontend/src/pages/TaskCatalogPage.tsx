import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Drawer,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
  Popconfirm,
} from "antd";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import {
  activateTask,
  createTask,
  deactivateTask,
  listStages,
  listTasks,
  updateTask,
  type Stage,
  type Task,
  type TaskCreate,
  type TaskUpdate,
} from "../api/client";

const CRITICAL_OPTS = [
  { value: "🔴", label: "🔴 关键" },
  { value: "🟡", label: "🟡 重要" },
  { value: "🟢", label: "🟢 一般" },
];

function errMsg(e: unknown): string {
  const err = e as { response?: { data?: { detail?: { message?: string } } } };
  return err.response?.data?.detail?.message ?? "操作失败";
}

export default function TaskCatalogPage() {
  const { user: me } = useAuth();
  const [stages, setStages] = useState<Stage[]>([]);
  const [stageId, setStageId] = useState<number | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [showInactive, setShowInactive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editTask, setEditTask] = useState<Task | null>(null);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const reloadStages = () =>
    listStages()
      .then((s) => {
        setStages(s);
        if (stageId == null && s.length) setStageId(s[0].stage_id);
      })
      .catch((e) => setError(errMsg(e)));

  const reloadTasks = (sid: number | null = stageId) => {
    if (sid == null) return;
    setLoading(true);
    listTasks({ stage_id: sid, include_inactive: showInactive })
      .then(setTasks)
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    reloadStages();
  }, []);

  useEffect(() => {
    reloadTasks();
  }, [stageId, showInactive]);

  if (me && me.role !== "admin") {
    return <Navigate to="/ops" replace />;
  }

  // 父任务 / 插入参照：本阶段启用任务（由后端校验同级关系）
  const parentOptions = tasks.filter((t) => t.is_active !== 0);

  const onCreate = async () => {
    try {
      const v = await createForm.validateFields();
      const body: TaskCreate = {
        stage_id: stageId!,
        task_name: v.task_name,
        owner: v.owner,
        critical_path: v.critical_path,
        default_days: v.default_days ?? 0,
        description: v.description,
        parent_task_id: v.parent_task_id ?? null,
        insert_before_task_id: v.insert_before_task_id ?? null,
      };
      await createTask(body);
      message.success("已新增任务（同级编号已自动顺移）");
      setCreateOpen(false);
      createForm.resetFields();
      reloadTasks();
      reloadStages();
    } catch (e) {
      if ((e as { errorFields?: unknown }).errorFields) return;
      message.error(errMsg(e));
    }
  };

  const onEdit = async () => {
    if (!editTask) return;
    try {
      const v = await editForm.validateFields();
      const body: TaskUpdate = {
        task_name: v.task_name,
        owner: v.owner,
        critical_path: v.critical_path,
        default_days: v.default_days,
        description: v.description,
      };
      await updateTask(editTask.task_id, body);
      message.success("已保存");
      setEditTask(null);
      reloadTasks();
    } catch (e) {
      if ((e as { errorFields?: unknown }).errorFields) return;
      message.error(errMsg(e));
    }
  };

  return (
    <div>
      <Typography.Title level={3}>任务清单</Typography.Title>
      <Typography.Paragraph type="secondary">
        管理员维护标准工序：新增时自动顺移同级编号；删除为停用（保留历史进度）。插入会改动已有
        task_code，若对照 Excel 映射请同步更新。
      </Typography.Paragraph>
      {error && <Alert type="error" message={error} style={{ marginBottom: 12 }} />}
      <Space wrap style={{ marginBottom: 16 }}>
        <Select
          style={{ minWidth: 280 }}
          value={stageId ?? undefined}
          options={stages.map((s) => ({
            value: s.stage_id,
            label: `${s.stage_id}. ${s.stage_name}（${s.task_count}）`,
          }))}
          onChange={(v) => setStageId(v)}
        />
        <Switch
          checked={showInactive}
          onChange={setShowInactive}
          checkedChildren="含停用"
          unCheckedChildren="仅启用"
        />
        <Button
          type="primary"
          disabled={stageId == null}
          onClick={() => {
            createForm.resetFields();
            createForm.setFieldsValue({
              critical_path: "🟢",
              default_days: 5,
              owner: "客户主导",
            });
            setCreateOpen(true);
          }}
        >
          新增任务
        </Button>
      </Space>
      <Table
        rowKey="task_id"
        loading={loading}
        dataSource={tasks}
        size="small"
        pagination={{ pageSize: 50 }}
        columns={[
          {
            title: "编号",
            dataIndex: "task_code",
            width: 100,
            render: (c: string | null, r: Task) => (
              <Space>
                <span>{c}</span>
                {r.is_active === 0 && <Tag>已停用</Tag>}
              </Space>
            ),
          },
          { title: "名称", dataIndex: "task_name" },
          { title: "责任方", dataIndex: "owner", width: 140 },
          {
            title: "关键",
            dataIndex: "critical_path",
            width: 70,
          },
          { title: "工期", dataIndex: "default_days", width: 70 },
          {
            title: "操作",
            width: 200,
            render: (_: unknown, r: Task) => (
              <Space>
                <Button
                  type="link"
                  size="small"
                  onClick={() => {
                    setEditTask(r);
                    editForm.setFieldsValue({
                      task_name: r.task_name,
                      owner: r.owner,
                      critical_path: r.critical_path,
                      default_days: r.default_days,
                      description: r.description,
                    });
                  }}
                >
                  编辑
                </Button>
                {r.is_active !== 0 ? (
                  <Popconfirm
                    title="停用该任务？"
                    description="不会删除进度记录；列表默认隐藏。"
                    onConfirm={async () => {
                      try {
                        await deactivateTask(r.task_id);
                        message.success("已停用");
                        reloadTasks();
                        reloadStages();
                      } catch (e) {
                        message.error(errMsg(e));
                      }
                    }}
                  >
                    <Button type="link" size="small" danger>
                      停用
                    </Button>
                  </Popconfirm>
                ) : (
                  <Button
                    type="link"
                    size="small"
                    onClick={async () => {
                      try {
                        await activateTask(r.task_id);
                        message.success("已恢复");
                        reloadTasks();
                        reloadStages();
                      } catch (e) {
                        message.error(errMsg(e));
                      }
                    }}
                  >
                    恢复
                  </Button>
                )}
              </Space>
            ),
          },
        ]}
      />

      <Drawer
        title="新增任务"
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        width={480}
        extra={
          <Button type="primary" onClick={onCreate}>
            提交
          </Button>
        }
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="task_name"
            label="任务名称"
            rules={[{ required: true, message: "必填" }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="parent_task_id" label="父任务（空=阶段下一级，如 2.N）">
            <Select
              allowClear
              placeholder="不选则为阶段一级任务"
              options={parentOptions.map((t) => ({
                value: t.task_id,
                label: `${t.task_code} ${t.task_name}`,
              }))}
            />
          </Form.Item>
          <Form.Item
            name="insert_before_task_id"
            label="插入到该同级任务之前（空=追加末尾）"
          >
            <Select
              allowClear
              placeholder="追加到同级末尾"
              options={parentOptions.map((t) => ({
                value: t.task_id,
                label: `${t.task_code} ${t.task_name}`,
              }))}
            />
          </Form.Item>
          <Form.Item name="owner" label="责任方" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="critical_path" label="关键路径" rules={[{ required: true }]}>
            <Select options={CRITICAL_OPTS} />
          </Form.Item>
          <Form.Item name="default_days" label="默认工期（天）">
            <InputNumber min={0} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Drawer>

      <Drawer
        title={editTask ? `编辑 ${editTask.task_code}` : "编辑"}
        open={!!editTask}
        onClose={() => setEditTask(null)}
        width={480}
        extra={
          <Button type="primary" onClick={onEdit}>
            保存
          </Button>
        }
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="编号由系统管理，编辑页不可改 task_code"
        />
        <Form form={editForm} layout="vertical">
          <Form.Item name="task_name" label="任务名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="owner" label="责任方" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="critical_path" label="关键路径" rules={[{ required: true }]}>
            <Select options={CRITICAL_OPTS} />
          </Form.Item>
          <Form.Item name="default_days" label="默认工期（天）">
            <InputNumber min={0} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Drawer>
    </div>
  );
}
