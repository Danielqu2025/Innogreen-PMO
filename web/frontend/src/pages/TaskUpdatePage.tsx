import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Form,
  Input,
  Select,
  Space,
  Typography,
  message,
} from "antd";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type Progress, type Project, type Task } from "../api/client";

const STATUS_OPTIONS = ["待开始", "进行中", "已完成", "已跳过", "卡点"];

type FormValues = {
  status: string;
  assigned_to?: string;
  blocker_note?: string;
};

export default function TaskUpdatePage() {
  const { id, taskId } = useParams();
  const navigate = useNavigate();
  const [form] = Form.useForm<FormValues>();
  const [project, setProject] = useState<Project | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const status = Form.useWatch("status", form);

  useEffect(() => {
    if (!id || !taskId) return;
    setLoading(true);
    Promise.all([
      api.get<Project>(`/api/ops/projects/${id}`),
      api.get<Task>(`/api/ops/tasks/${taskId}`),
      api.get<Progress[]>(`/api/ops/projects/${id}/progress`),
    ])
      .then(([p, t, pr]) => {
        setProject(p.data);
        setTask(t.data);
        const existing = pr.data.find((row) => row.task_id === Number(taskId));
        form.setFieldsValue({
          status: existing?.status ?? "待开始",
          assigned_to: existing?.assigned_to ?? undefined,
          blocker_note: existing?.blocker_note ?? undefined,
        });
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id, taskId, form]);

  const onFinish = async (values: FormValues) => {
    if (!id || !taskId) return;
    setSubmitting(true);
    try {
      await api.put(`/api/ops/projects/${id}/tasks/${taskId}`, {
        status: values.status,
        assigned_to: values.assigned_to || null,
        blocker_note: values.status === "卡点" ? values.blocker_note || null : null,
      });
      message.success("进度已更新");
      navigate(`/ops/projects/${id}`);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: { message?: string } } } };
      message.error(err.response?.data?.detail?.message ?? "更新失败");
    } finally {
      setSubmitting(false);
    }
  };

  if (error) return <Alert type="error" message={error} />;
  if (loading || !project || !task) {
    return <Typography.Text>加载中…</Typography.Text>;
  }

  return (
    <div>
      <Typography.Title level={3}>更新任务进度</Typography.Title>
      <Typography.Paragraph type="secondary">
        {project.project_code} · {task.task_code} {task.task_name}
      </Typography.Paragraph>

      <Form
        form={form}
        layout="vertical"
        onFinish={onFinish}
        style={{ maxWidth: 480 }}
      >
        <Form.Item
          name="status"
          label="状态"
          rules={[{ required: true, message: "请选择状态" }]}
        >
          <Select options={STATUS_OPTIONS.map((s) => ({ label: s, value: s }))} />
        </Form.Item>

        <Form.Item name="assigned_to" label="负责人">
          <Input placeholder="可选" />
        </Form.Item>

        {status === "卡点" && (
          <Form.Item
            name="blocker_note"
            label="卡点说明"
            rules={[{ required: true, message: "卡点状态需填写说明" }]}
          >
            <Input.TextArea rows={3} placeholder="描述卡点原因与预计解决时间" />
          </Form.Item>
        )}

        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={submitting}>
              保存
            </Button>
            <Link to={`/ops/projects/${id}`}>
              <Button>取消</Button>
            </Link>
          </Space>
        </Form.Item>
      </Form>
    </div>
  );
}
