import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Button,
  DatePicker,
  Form,
  Input,
  Select,
  Space,
  Timeline,
  Typography,
  message,
} from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  api,
  createTaskJournal,
  listTaskJournal,
  type JournalEntry,
  type Progress,
  type Project,
  type Task,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";

const STATUS_OPTIONS = ["待开始", "进行中", "已完成", "已跳过", "卡点"];

type FormValues = {
  status: string;
  assigned_to?: string;
  vendor?: string;
  blocker_note?: string;
  planned_start?: Dayjs | null;
  planned_end?: Dayjs | null;
  started_at?: Dayjs | null;
  completed_at?: Dayjs | null;
};

type JournalForm = {
  week_start: Dayjs;
  note: string;
  week_label?: string;
};

function toDay(v?: string | null): Dayjs | undefined {
  if (!v) return undefined;
  const d = dayjs(v);
  return d.isValid() ? d : undefined;
}

function toIso(v?: Dayjs | null): string | null {
  if (!v) return null;
  return v.format("YYYY-MM-DD HH:mm:ss");
}

export default function TaskUpdatePage() {
  const { id, taskId } = useParams();
  const navigate = useNavigate();
  const { canWrite } = useAuth();
  const [form] = Form.useForm<FormValues>();
  const [journalForm] = Form.useForm<JournalForm>();
  const [project, setProject] = useState<Project | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [journals, setJournals] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [journalSubmitting, setJournalSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const status = Form.useWatch("status", form);

  const reloadJournal = useCallback(() => {
    if (!id || !taskId) return;
    listTaskJournal(Number(id), Number(taskId), 50)
      .then(setJournals)
      .catch(() => setJournals([]));
  }, [id, taskId]);

  useEffect(() => {
    if (!id || !taskId) return;
    setLoading(true);
    Promise.all([
      api.get<Project>(`/api/ops/projects/${id}`),
      api.get<Task>(`/api/ops/tasks/${taskId}`),
      api.get<Progress[]>(`/api/ops/projects/${id}/progress`),
      listTaskJournal(Number(id), Number(taskId), 50),
    ])
      .then(([p, t, pr, j]) => {
        setProject(p.data);
        setTask(t.data);
        setJournals(j);
        const existing = pr.data.find((row) => row.task_id === Number(taskId));
        form.setFieldsValue({
          status: existing?.status ?? "待开始",
          assigned_to: existing?.assigned_to ?? undefined,
          vendor: existing?.vendor ?? undefined,
          blocker_note: existing?.blocker_note ?? undefined,
          planned_start: toDay(existing?.planned_start),
          planned_end: toDay(existing?.planned_end),
          started_at: toDay(existing?.started_at),
          completed_at: toDay(existing?.completed_at),
        });
        journalForm.setFieldsValue({ week_start: dayjs() });
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id, taskId, form, journalForm]);

  const onFinish = async (values: FormValues) => {
    if (!id || !taskId) return;
    setSubmitting(true);
    try {
      await api.put(`/api/ops/projects/${id}/tasks/${taskId}`, {
        status: values.status,
        assigned_to: values.assigned_to || null,
        vendor: values.vendor || null,
        blocker_note: values.status === "卡点" ? values.blocker_note || null : null,
        planned_start: toIso(values.planned_start),
        planned_end: toIso(values.planned_end),
        started_at: toIso(values.started_at),
        completed_at: toIso(values.completed_at),
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

  const onAddJournal = async (values: JournalForm) => {
    if (!id || !taskId) return;
    setJournalSubmitting(true);
    try {
      await createTaskJournal(Number(id), Number(taskId), {
        week_start: values.week_start.format("YYYY-MM-DD"),
        note: values.note,
        week_label: values.week_label || undefined,
      });
      message.success("周记已追加");
      journalForm.resetFields(["note", "week_label"]);
      journalForm.setFieldsValue({ week_start: dayjs() });
      reloadJournal();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: { message?: string } } } };
      message.error(err.response?.data?.detail?.message ?? "追加失败");
    } finally {
      setJournalSubmitting(false);
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
        style={{ maxWidth: 520 }}
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

        <Form.Item name="vendor" label="第三方单位">
          <Input placeholder="可选" />
        </Form.Item>

        <Form.Item name="planned_start" label="计划开始">
          <DatePicker style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item name="planned_end" label="计划完成">
          <DatePicker style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item name="started_at" label="实际开始">
          <DatePicker style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item name="completed_at" label="实际完成">
          <DatePicker style={{ width: "100%" }} />
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

      <Typography.Title level={4} style={{ marginTop: 32 }}>
        周进展时间线
      </Typography.Title>
      {canWrite && (
        <Form
          form={journalForm}
          layout="vertical"
          onFinish={onAddJournal}
          style={{ maxWidth: 520, marginBottom: 16 }}
        >
          <Form.Item
            name="week_start"
            label="周起始日"
            rules={[{ required: true, message: "必填" }]}
          >
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="week_label" label="周标签（可选）">
            <Input placeholder="如：7月20日-7月26日" />
          </Form.Item>
          <Form.Item
            name="note"
            label="本周进展"
            rules={[{ required: true, message: "请填写内容" }]}
          >
            <Input.TextArea rows={3} placeholder="本周做了什么 / 卡在哪里" />
          </Form.Item>
          <Button type="dashed" htmlType="submit" loading={journalSubmitting}>
            追加周记
          </Button>
        </Form>
      )}
      {journals.length === 0 ? (
        <Typography.Text type="secondary">暂无周记</Typography.Text>
      ) : (
        <Timeline
          items={journals.map((j) => ({
            children: (
              <div>
                <Typography.Text strong>
                  {j.week_start}
                  {j.week_label ? ` · ${j.week_label}` : ""}
                </Typography.Text>
                <div>
                  <Typography.Text type="secondary">
                    {j.source === "excel_import" ? "Excel导入" : "手工"}
                    {j.actor ? ` · ${j.actor}` : ""}
                  </Typography.Text>
                </div>
                <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}>
                  {j.note}
                </Typography.Paragraph>
              </div>
            ),
          }))}
        />
      )}
    </div>
  );
}
