import { useState } from "react";
import { Alert, Button, Checkbox, Space, Typography, message } from "antd";
import { DownloadOutlined, DatabaseOutlined } from "@ant-design/icons";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import {
  downloadExportDb,
  downloadExportExcel,
  type ExportSheetKey,
} from "../api/client";

const SHEET_OPTIONS: { key: ExportSheetKey; label: string }[] = [
  { key: "stages", label: "阶段定义" },
  { key: "tasks", label: "任务明细" },
  { key: "projects", label: "企业档案" },
  { key: "progress", label: "任务进度" },
  { key: "pitfalls", label: "避坑指南" },
];

const ALL_KEYS = SHEET_OPTIONS.map((o) => o.key);

export default function DataExportPage() {
  const { user: me } = useAuth();
  const [excelLoading, setExcelLoading] = useState(false);
  const [dbLoading, setDbLoading] = useState(false);
  const [selected, setSelected] = useState<ExportSheetKey[]>([...ALL_KEYS]);

  if (me && me.role !== "admin" && me.role !== "operator") {
    return <Navigate to="/ops" replace />;
  }

  const onDownloadExcel = async () => {
    if (!selected.length) {
      message.warning("请至少选择一个数据集");
      return;
    }
    setExcelLoading(true);
    try {
      await downloadExportExcel(selected);
      message.success("Excel 导出成功");
    } catch {
      message.error("Excel 导出失败");
    } finally {
      setExcelLoading(false);
    }
  };

  const onDownloadDb = async () => {
    setDbLoading(true);
    try {
      await downloadExportDb();
      message.success("数据库导出成功");
    } catch {
      message.error("数据库导出失败");
    } finally {
      setDbLoading(false);
    }
  };

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Typography.Title level={4} style={{ margin: 0 }}>
        数据导出
      </Typography.Title>

      <Alert
        type="info"
        showIcon
        message="导出为 Excel（.xlsx）多 sheet 工作簿"
        description="勾选需要导出的数据集；默认全选。"
      />
      <Checkbox.Group
        value={selected}
        onChange={(vals) => setSelected(vals as ExportSheetKey[])}
        options={SHEET_OPTIONS.map((o) => ({ label: o.label, value: o.key }))}
        style={{ display: "flex", flexDirection: "column", gap: 8 }}
      />
      <Space>
        <Button type="link" size="small" onClick={() => setSelected([...ALL_KEYS])}>
          全选
        </Button>
        <Button type="link" size="small" onClick={() => setSelected([])}>
          清空
        </Button>
      </Space>
      <Button
        type="primary"
        icon={<DownloadOutlined />}
        loading={excelLoading}
        disabled={!selected.length}
        onClick={onDownloadExcel}
      >
        下载 Excel
      </Button>

      <Alert
        type="info"
        showIcon
        message="导出为 SQLite 数据库（.db）"
        description="使用 Online Backup 生成事务一致快照，适合整库备份或迁移。导入侧可全量替换当前库（仅管理员）。"
      />
      <Button
        icon={<DatabaseOutlined />}
        loading={dbLoading}
        onClick={onDownloadDb}
      >
        下载 SQLite（.db）
      </Button>
    </Space>
  );
}
