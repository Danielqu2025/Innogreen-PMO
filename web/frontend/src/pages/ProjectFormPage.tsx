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
import { api, type Project, type Stage } from "../api/client";

const BUSINESS_TYPES = ["研发", "中试", "小规模生产"];
const PROJECT_STATUSES = ["未开始", "进行中", "卡点", "已完成", "已退园"];

type CreateValues = {
  project_code: string;
  company_name: string;
  short_name?: string;
  business_type?: string;
  building?: string;
  notes?: string;
};

type EditValues = {
  short_name?: string;
  business_type?: string;
  building?: string;
  project_status?: string;
  current_stage_id?: number;
  notes?: string;
};

export default function ProjectFormPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = !id;
  const [createForm] = Form.useForm<CreateValues>();
  const [editForm] = Form.useForm<EditValues>();
  const [project, setProject] = useState<Project | null>(null);
  const [stages, setStages] = useState<Stage[]>([]);
  const [loading, setLoading] = useState(!isNew);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Stage[]>("/api/ops/stages")
      .then((r) => setStages(r.data))
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (isNew || !id) return;
    setLoading(true);
    api
      .get<Project>(`/api/ops/projects/${id}`)
      .then((r) => {
        setProject(r.data);
        editForm.setFieldsValue({
          short_name: r.data.short_name ?? undefined,
          business_type: r.data.business_type ?? undefined,
          building: r.data.building ?? undefined,
          project_status: r.data.project_status,
          current_stage_id: r.data.current_stage_id ?? undefined,
          notes: r.data.notes ?? undefined,
        });
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id, isNew, editForm]);

  const onCodeChange = (code: string) => {
    const currentName = createForm.getFieldValue("company_name");
    if (!currentName || currentName === createForm.getFieldValue("project_code")) {
      createForm.setFieldValue("company_name", code);
    }
  };

  const submitCreate = async (values: CreateValues) => {
    setSubmitting(true);
    try {
      const r = await api.post<Project>("/api/ops/projects", {
        project_code: values.project_code.trim(),
        company_name: values.company_name.trim(),
        short_name: values.short_name?.trim() || null,
        business_type: values.business_type || null,
        building: values.building?.trim() || null,
        notes: values.notes?.trim() || null,
      });
      message.success("企业已创建");
      navigate(`/ops/projects/${r.data.project_id}`);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: { message?: string } } } };
      message.error(err.response?.data?.detail?.message ?? "创建失败");
    } finally {
      setSubmitting(false);
    }
  };

  const submitEdit = async (values: EditValues) => {
    if (!id) return;
    setSubmitting(true);
    try {
      await api.patch(`/api/ops/projects/${id}`, {
        short_name: values.short_name?.trim() || null,
        business_type: values.business_type || null,
        building: values.building?.trim() || null,
        project_status: values.project_status,
        current_stage_id: values.current_stage_id ?? null,
        notes: values.notes?.trim() || null,
      });
      message.success("企业信息已更新");
      navigate(`/ops/projects/${id}`);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: { message?: string } } } };
      message.error(err.response?.data?.detail?.message ?? "更新失败");
    } finally {
      setSubmitting(false);
    }
  };

  if (error) return <Alert type="error" message={error} />;
  if (!isNew && (loading || !project)) {
    return <Typography.Text>加载中…</Typography.Text>;
  }

  return (
    <div>
      <Typography.Title level={3}>
        {isNew ? "新增企业" : `编辑企业 · ${project?.project_code}`}
      </Typography.Title>

      {isNew ? (
        <Form
          form={createForm}
          layout="vertical"
          onFinish={submitCreate}
          style={{ maxWidth: 480 }}
          initialValues={{ business_type: "研发" }}
        >
          <Form.Item
            name="project_code"
            label="企业编号"
            rules={[{ required: true, message: "请输入编号，如 ENT-04" }]}
          >
            <Input placeholder="ENT-04" onChange={(e) => onCodeChange(e.target.value)} />
          </Form.Item>
          <Form.Item
            name="company_name"
            label="企业名称"
            extra="脱敏场景可与编号相同"
            rules={[{ required: true, message: "请输入企业名称" }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="short_name" label="简称">
            <Input placeholder="可选，默认同编号" />
          </Form.Item>
          <Form.Item name="business_type" label="业务类型">
            <Select
              allowClear
              options={BUSINESS_TYPES.map((t) => ({ label: t, value: t }))}
            />
          </Form.Item>
          <Form.Item name="building" label="楼栋">
            <Input placeholder="如 F6d-1" />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={submitting}>
                创建
              </Button>
              <Link to="/ops/projects">
                <Button>取消</Button>
              </Link>
            </Space>
          </Form.Item>
        </Form>
      ) : (
        <Form
          form={editForm}
          layout="vertical"
          onFinish={submitEdit}
          style={{ maxWidth: 480 }}
        >
          <Form.Item label="企业编号">
            <Input value={project?.project_code} disabled />
          </Form.Item>
          <Form.Item label="进度">
            <Input value={`${project?.progress_percent ?? 0}%（由任务进度自动计算）`} disabled />
          </Form.Item>
          <Form.Item name="short_name" label="简称">
            <Input />
          </Form.Item>
          <Form.Item name="business_type" label="业务类型">
            <Select
              allowClear
              options={BUSINESS_TYPES.map((t) => ({ label: t, value: t }))}
            />
          </Form.Item>
          <Form.Item name="building" label="楼栋">
            <Input />
          </Form.Item>
          <Form.Item name="project_status" label="项目状态">
            <Select options={PROJECT_STATUSES.map((s) => ({ label: s, value: s }))} />
          </Form.Item>
          <Form.Item name="current_stage_id" label="当前阶段">
            <Select
              allowClear
              options={stages.map((s) => ({
                label: s.stage_name,
                value: s.stage_id,
              }))}
            />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={3} />
          </Form.Item>
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
      )}
    </div>
  );
}
