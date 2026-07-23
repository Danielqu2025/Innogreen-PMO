import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Col,
  DatePicker,
  Form,
  Input,
  Popconfirm,
  Row,
  Select,
  Space,
  Timeline,
  Typography,
  message,
} from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { Link, useParams } from "react-router-dom";
import {
  api,
  createTaskJournal,
  deleteTaskJournal,
  listTaskJournal,
  updateTaskJournal,
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
  /** 当周周一 YYYY-MM-DD */
  week_key?: string;
  note?: string;
};

type WeekOption = {
  value: string;
  label: string;
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

/** 取所在周的周一 */
function mondayOf(d: Dayjs): Dayjs {
  const day = d.day(); // 0=周日
  const diff = day === 0 ? -6 : 1 - day;
  return d.add(diff, "day").startOf("day");
}

function weekLabelOf(monday: Dayjs, indexFromThisWeek: number): string {
  const sunday = monday.add(6, "day");
  const range = `${monday.format("YYYY-MM-DD")}~${sunday.format("MM-DD")}`;
  const name =
    indexFromThisWeek === 0
      ? "本周"
      : indexFromThisWeek === 1
        ? "上周"
        : `${indexFromThisWeek}周前`;
  return `${name}（${range}）`;
}

/** 本周 + 往前 4 周 */
function buildWeekOptions(now = dayjs()): WeekOption[] {
  const thisMonday = mondayOf(now);
  return [0, 1, 2, 3, 4].map((i) => {
    const mon = thisMonday.subtract(i, "week");
    return {
      value: mon.format("YYYY-MM-DD"),
      label: weekLabelOf(mon, i),
    };
  });
}

function labelForWeekKey(weekKey: string, options: WeekOption[]): string {
  const hit = options.find((o) => o.value === weekKey);
  if (hit) return hit.label;
  const mon = dayjs(weekKey);
  if (!mon.isValid()) return weekKey;
  return `${mon.format("YYYY-MM-DD")}~${mon.add(6, "day").format("MM-DD")}`;
}

export default function TaskUpdatePage() {
  const { id, taskId } = useParams();
  const { canWrite } = useAuth();
  const [form] = Form.useForm<FormValues>();
  const [journalForm] = Form.useForm<JournalForm>();
  const [project, setProject] = useState<Project | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [journals, setJournals] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editWeekKey, setEditWeekKey] = useState<string>("");
  const [editNote, setEditNote] = useState("");
  const [journalBusy, setJournalBusy] = useState(false);
  const status = Form.useWatch("status", form);

  const weekOptions = useMemo(() => buildWeekOptions(), []);

  const editWeekOptions = useMemo(() => {
    if (!editWeekKey || weekOptions.some((o) => o.value === editWeekKey)) {
      return weekOptions;
    }
    return [
      { value: editWeekKey, label: labelForWeekKey(editWeekKey, weekOptions) },
      ...weekOptions,
    ];
  }, [editWeekKey, weekOptions]);

  const reloadJournal = useCallback(() => {
    if (!id || !taskId) return;
    listTaskJournal(Number(id), Number(taskId), 50)
      .then(setJournals)
      .catch(() => setJournals([]));
  }, [id, taskId]);

  const startEdit = (j: JournalEntry) => {
    const key = mondayOf(dayjs(j.week_start)).format("YYYY-MM-DD");
    setEditingId(j.journal_id);
    setEditWeekKey(key);
    setEditNote(j.note);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditWeekKey("");
    setEditNote("");
  };

  const saveEdit = async () => {
    if (!id || !taskId || editingId == null) return;
    const note = editNote.trim();
    if (!editWeekKey) {
      message.error("请选择周标签");
      return;
    }
    if (!note) {
      message.error("周记内容不能为空");
      return;
    }
    setJournalBusy(true);
    try {
      await updateTaskJournal(Number(id), Number(taskId), editingId, {
        week_start: editWeekKey,
        week_label: labelForWeekKey(editWeekKey, weekOptions),
        note,
      });
      message.success("周记已更新");
      cancelEdit();
      reloadJournal();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: { message?: string } } } };
      message.error(err.response?.data?.detail?.message ?? "更新失败");
    } finally {
      setJournalBusy(false);
    }
  };

  const removeJournal = async (journalId: number) => {
    if (!id || !taskId) return;
    setJournalBusy(true);
    try {
      await deleteTaskJournal(Number(id), Number(taskId), journalId);
      message.success("周记已删除");
      if (editingId === journalId) cancelEdit();
      reloadJournal();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: { message?: string } } } };
      message.error(err.response?.data?.detail?.message ?? "删除失败");
    } finally {
      setJournalBusy(false);
    }
  };

  useEffect(() => {
    if (!id || !taskId) return;
    setLoading(true);
    const thisMonday = mondayOf(dayjs()).format("YYYY-MM-DD");
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
        journalForm.setFieldsValue({ week_key: thisMonday });
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id, taskId, form, journalForm]);

  /** 保存进度；若填写了本周进展，则一并追加周记（留在本页） */
  const onSave = async () => {
    if (!id || !taskId) return;
    try {
      const values = await form.validateFields();
      const j = journalForm.getFieldsValue();
      const note = (j.note ?? "").trim();
      if (note && !j.week_key) {
        message.error("填写本周进展时请选择周标签");
        return;
      }

      setSubmitting(true);
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

      if (note && j.week_key) {
        await createTaskJournal(Number(id), Number(taskId), {
          week_start: j.week_key,
          note,
          week_label: labelForWeekKey(j.week_key, weekOptions),
        });
        journalForm.resetFields(["note"]);
        journalForm.setFieldsValue({
          week_key: mondayOf(dayjs()).format("YYYY-MM-DD"),
        });
        reloadJournal();
        message.success("进度与周记已保存");
      } else {
        message.success("进度已更新");
      }
    } catch (e: unknown) {
      if (e && typeof e === "object" && "errorFields" in e) {
        return;
      }
      const err = e as { response?: { data?: { detail?: { message?: string } } } };
      message.error(err.response?.data?.detail?.message ?? "保存失败");
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
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 16,
          marginBottom: 8,
        }}
      >
        <div>
          <Typography.Title level={3} style={{ marginTop: 0, marginBottom: 8 }}>
            更新任务进度
          </Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
            {project.short_name || project.project_code} · {task.task_code} {task.task_name}
          </Typography.Paragraph>
        </div>
        <Link to={`/ops/projects/${id}`}>
          <Button>返回</Button>
        </Link>
      </div>

      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Row gutter={[16, 0]}>
          <Col xs={24} sm={8} lg={5}>
            <Form.Item
              name="status"
              label="状态"
              rules={[{ required: true, message: "请选择状态" }]}
            >
              <Select
                style={{ maxWidth: 128 }}
                options={STATUS_OPTIONS.map((s) => ({ label: s, value: s }))}
              />
            </Form.Item>
          </Col>
          <Col xs={24} sm={8} lg={6}>
            <Form.Item name="assigned_to" label="负责人">
              <Input style={{ maxWidth: 200 }} placeholder="可选" maxLength={20} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={8} lg={13}>
            <Form.Item name="vendor" label="第三方单位">
              <Input placeholder="可选" />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={[16, 0]}>
          <Col xs={24} sm={12}>
            <Form.Item name="planned_start" label="计划开始">
              <DatePicker style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="planned_end" label="计划完成">
              <DatePicker style={{ width: "100%" }} />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={[16, 0]}>
          <Col xs={24} sm={12}>
            <Form.Item name="started_at" label="实际开始">
              <DatePicker style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="completed_at" label="实际完成">
              <DatePicker style={{ width: "100%" }} />
            </Form.Item>
          </Col>
        </Row>

        {status === "卡点" && (
          <Form.Item
            name="blocker_note"
            label="卡点说明"
            rules={[{ required: true, message: "卡点状态需填写说明" }]}
          >
            <Input.TextArea rows={3} placeholder="描述卡点原因与预计解决时间" />
          </Form.Item>
        )}
      </Form>

      <Typography.Title level={4} style={{ marginTop: 32 }}>
        周进展时间线
      </Typography.Title>
      {canWrite && (
        <Form form={journalForm} layout="vertical" style={{ marginBottom: 16 }}>
          <Form.Item name="week_key" label="周标签">
            <Select
              style={{ maxWidth: 360 }}
              options={weekOptions}
              placeholder="选择周次"
            />
          </Form.Item>
          <Form.Item name="note" label="本周进展（可选，与进度一并保存）">
            <Input.TextArea
              rows={3}
              placeholder="本周做了什么 / 卡在哪里；不填则只保存任务进度"
            />
          </Form.Item>
        </Form>
      )}
      {journals.length > 0 && (
        <Timeline
          items={journals.map((j) => {
            const editing = editingId === j.journal_id;
            return {
              children: (
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 16,
                    alignItems: "flex-start",
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    {editing ? (
                      <Space direction="vertical" style={{ width: "100%" }} size={8}>
                        <Select
                          value={editWeekKey}
                          onChange={setEditWeekKey}
                          options={editWeekOptions}
                          style={{ maxWidth: 360, width: "100%" }}
                        />
                        <Input.TextArea
                          rows={3}
                          value={editNote}
                          onChange={(e) => setEditNote(e.target.value)}
                        />
                      </Space>
                    ) : (
                      <>
                        <Typography.Text strong>
                          {j.week_label ||
                            labelForWeekKey(
                              mondayOf(dayjs(j.week_start)).format("YYYY-MM-DD"),
                              weekOptions,
                            )}
                        </Typography.Text>
                        <div>
                          <Typography.Text type="secondary">
                            {j.source === "excel_import" ? "Excel导入" : "手工"}
                            {j.actor ? ` · ${j.actor}` : ""}
                          </Typography.Text>
                        </div>
                        <Typography.Paragraph
                          style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}
                        >
                          {j.note}
                        </Typography.Paragraph>
                      </>
                    )}
                  </div>
                  {canWrite && (
                    <Space direction="vertical" size={4} style={{ flexShrink: 0 }}>
                      <Button
                        type="link"
                        size="small"
                        disabled={journalBusy}
                        onClick={() => {
                          if (editing) void saveEdit();
                          else startEdit(j);
                        }}
                      >
                        更新
                      </Button>
                      <Button
                        type="link"
                        size="small"
                        disabled={!editing || journalBusy}
                        onClick={cancelEdit}
                      >
                        取消
                      </Button>
                      <Popconfirm
                        title="确定删除这条周记？"
                        okText="删除"
                        cancelText="取消"
                        onConfirm={() => void removeJournal(j.journal_id)}
                      >
                        <Button type="link" size="small" danger disabled={journalBusy}>
                          删除
                        </Button>
                      </Popconfirm>
                    </Space>
                  )}
                </div>
              ),
            };
          })}
        />
      )}

      <Space style={{ marginTop: 32 }}>
        <Button type="primary" loading={submitting} onClick={() => void onSave()}>
          保存
        </Button>
        <Link to={`/ops/projects/${id}`}>
          <Button>取消</Button>
        </Link>
        <Link to={`/ops/projects/${id}`}>
          <Button>返回</Button>
        </Link>
      </Space>
    </div>
  );
}
