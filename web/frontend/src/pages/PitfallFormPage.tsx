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
import { Link, useNavigate } from "react-router-dom";
import { api, type Stage } from "../api/client";

const IMPACT_LEVELS = ["极高", "高", "中", "低"];
const REF_TYPES = ["常见", "偶尔", "罕见"];

type FormValues = {
  stage_ref: string;
  wrong_action: string;
  right_action: string;
  standard_ref?: string;
  impact_level: string;
  trigger_condition?: string;
  remediation?: string;
  notes?: string;
  ref_type: string;
};

export default function PitfallFormPage() {
  const navigate = useNavigate();
  const [form] = Form.useForm<FormValues>();
  const [stages, setStages] = useState<Stage[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Stage[]>("/api/ops/stages")
      .then((r) => setStages(r.data))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const onFinish = async (values: FormValues) => {
    setSubmitting(true);
    try {
      const r = await api.post("/api/ops/pitfalls", {
        stage_ref: values.stage_ref,
        wrong_action: values.wrong_action.trim(),
        right_action: values.right_action.trim(),
        standard_ref: values.standard_ref?.trim() || null,
        impact_level: values.impact_level,
        trigger_condition: values.trigger_condition?.trim() || null,
        remediation: values.remediation?.trim() || null,
        notes: values.notes?.trim() || null,
        ref_type: values.ref_type,
      });
      message.success("避坑指南已录入");
      navigate(`/ops/pitfalls/${r.data.pitfall_id}`);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: { message?: string } } } };
      message.error(err.response?.data?.detail?.message ?? "录入失败");
    } finally {
      setSubmitting(false);
    }
  };

  if (error) return <Alert type="error" message={error} />;
  if (loading) return <Typography.Text>加载中…</Typography.Text>;

  return (
    <div>
      <Typography.Title level={3}>录入避坑指南</Typography.Title>
      <Form
        form={form}
        layout="vertical"
        onFinish={onFinish}
        style={{ maxWidth: 640 }}
        initialValues={{ impact_level: "中", ref_type: "常见" }}
      >
        <Form.Item
          name="stage_ref"
          label="关联阶段"
          rules={[{ required: true, message: "请选择阶段" }]}
        >
          <Select
            showSearch
            optionFilterProp="label"
            options={stages.map((s) => ({
              label: s.stage_name,
              value: s.stage_name,
            }))}
          />
        </Form.Item>
        <Form.Item
          name="wrong_action"
          label="错误做法"
          rules={[{ required: true, message: "请填写错误做法" }]}
        >
          <Input.TextArea rows={2} />
        </Form.Item>
        <Form.Item
          name="right_action"
          label="合规做法"
          rules={[{ required: true, message: "请填写合规做法" }]}
        >
          <Input.TextArea rows={2} />
        </Form.Item>
        <Form.Item name="standard_ref" label="依据/规范">
          <Input placeholder="法规条文或标准编号" />
        </Form.Item>
        <Form.Item name="impact_level" label="影响等级">
          <Select options={IMPACT_LEVELS.map((v) => ({ label: v, value: v }))} />
        </Form.Item>
        <Form.Item name="ref_type" label="阶段关联类型">
          <Select options={REF_TYPES.map((v) => ({ label: v, value: v }))} />
        </Form.Item>
        <Form.Item name="trigger_condition" label="触发条件">
          <Input.TextArea rows={2} />
        </Form.Item>
        <Form.Item name="remediation" label="补救建议">
          <Input.TextArea rows={2} />
        </Form.Item>
        <Form.Item name="notes" label="备注">
          <Input.TextArea rows={2} />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={submitting}>
              保存
            </Button>
            <Link to="/ops/pitfalls">
              <Button>取消</Button>
            </Link>
          </Space>
        </Form.Item>
      </Form>
    </div>
  );
}
