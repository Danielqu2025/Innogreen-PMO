import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  Form,
  InputNumber,
  Radio,
  Space,
  Switch,
  Typography,
  message,
} from "antd";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import {
  getJournalAlertSettings,
  updateJournalAlertSettings,
  type JournalAlertSettings,
} from "../api/client";

const STATUS_OPTIONS = [
  { label: "未开始", value: "未开始" },
  { label: "进行中", value: "进行中" },
  { label: "卡点", value: "卡点" },
  { label: "已完成", value: "已完成" },
  { label: "已退园", value: "已退园" },
];

export default function AlertSettingsPage() {
  const { user: me } = useAuth();
  const [form] = Form.useForm<JournalAlertSettings>();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mode = Form.useWatch("mode", form);

  useEffect(() => {
    getJournalAlertSettings()
      .then((data) => {
        form.setFieldsValue(data);
        setError(null);
      })
      .catch((e: Error) => setError(e.message || "加载失败"))
      .finally(() => setLoading(false));
  }, [form]);

  if (me && me.role !== "admin") {
    return <Navigate to="/ops" replace />;
  }

  const onSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const saved = await updateJournalAlertSettings(values);
      form.setFieldsValue(saved);
      message.success(`已保存（${saved.label ?? "预警机制"}）`);
    } catch (e) {
      if (e && typeof e === "object" && "errorFields" in e) return;
      message.error(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Space direction="vertical" size="large" style={{ width: "100%", maxWidth: 640 }}>
      <div>
        <Typography.Title level={4} style={{ margin: 0 }}>
          预警机制
        </Typography.Title>
        <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
          配置看板「周报异常」的判定规则。改动立即影响项目看板统计。
        </Typography.Paragraph>
      </div>

      {error && <Alert type="error" showIcon message={error} />}

      <Form
        form={form}
        layout="vertical"
        disabled={loading}
        initialValues={{
          enabled: true,
          statuses: ["进行中"],
          mode: "calendar_weeks",
          threshold: 1,
          count_missing: true,
        }}
      >
        <Form.Item name="enabled" label="启用周报异常统计" valuePropName="checked">
          <Switch checkedChildren="开" unCheckedChildren="关" />
        </Form.Item>

        <Form.Item
          name="statuses"
          label="适用项目状态"
          rules={[{ required: true, message: "至少选择一个状态" }]}
        >
          <Checkbox.Group options={STATUS_OPTIONS} />
        </Form.Item>

        <Form.Item name="mode" label="判定方式" rules={[{ required: true }]}>
          <Radio.Group>
            <Space direction="vertical">
              <Radio value="calendar_weeks">自然周：按周一起算，看最近周报是否覆盖到允许的落后周数</Radio>
              <Radio value="rolling_days">滚动天数：最近周报距今天数超过阈值即异常</Radio>
            </Space>
          </Radio.Group>
        </Form.Item>

        <Form.Item
          name="threshold"
          label={mode === "rolling_days" ? "阈值（天）" : "允许落后周数"}
          rules={[{ required: true, message: "请填写阈值" }]}
          extra={
            mode === "rolling_days"
              ? "例如 14：最近周报的 week_start 早于今天减去 14 天 → 异常"
              : "0 = 本周必须有周报；1 = 上周或本周即可；2 = 最多落后两周"
          }
        >
          <InputNumber min={mode === "rolling_days" ? 1 : 0} max={90} style={{ width: 120 }} />
        </Form.Item>

        <Form.Item
          name="count_missing"
          label="从未写过周报是否算异常"
          valuePropName="checked"
        >
          <Switch checkedChildren="算异常" unCheckedChildren="不算" />
        </Form.Item>

        <Button type="primary" loading={saving} onClick={onSave}>
          保存
        </Button>
      </Form>
    </Space>
  );
}
