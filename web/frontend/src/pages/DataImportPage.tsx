import { useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  Divider,
  Modal,
  Space,
  Switch,
  Typography,
  Upload,
  message,
} from "antd";
import {
  DownloadOutlined,
  InboxOutlined,
  UploadOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import {
  downloadImportTemplate,
  importDb,
  importExcel,
  type DbImportResult,
  type ImportSummary,
} from "../api/client";

function errMsg(e: unknown): string {
  const err = e as {
    response?: { data?: { detail?: { message?: string } } };
  };
  return err.response?.data?.detail?.message ?? "导入失败";
}

export default function DataImportPage() {
  const { user: me } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [dryRun, setDryRun] = useState(true);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const [tplLoading, setTplLoading] = useState(false);

  const [dbFile, setDbFile] = useState<File | null>(null);
  const [dbLoading, setDbLoading] = useState(false);
  const [dbAck, setDbAck] = useState(false);
  const [dbResult, setDbResult] = useState<DbImportResult | null>(null);

  const isAdmin = me?.role === "admin";
  const canExcel = me?.role === "admin" || me?.role === "operator";

  if (me && !canExcel) {
    return <Navigate to="/ops" replace />;
  }

  const onDownloadTemplate = async () => {
    setTplLoading(true);
    try {
      await downloadImportTemplate();
      message.success("模板已下载");
    } catch {
      message.error("模板下载失败");
    } finally {
      setTplLoading(false);
    }
  };

  const onSubmitExcel = async () => {
    if (!file) {
      message.warning("请先选择 Excel 文件");
      return;
    }
    setLoading(true);
    setSummary(null);
    try {
      const result = await importExcel(file, dryRun);
      setSummary(result);
      message.success(dryRun ? "试跑完成（未写库）" : "导入完成");
    } catch (e) {
      message.error(errMsg(e));
    } finally {
      setLoading(false);
    }
  };

  const onSubmitDb = () => {
    if (!dbFile) {
      message.warning("请先选择 .db 文件");
      return;
    }
    if (!dbAck) {
      message.warning("请先勾选确认：理解将全量替换当前数据库");
      return;
    }
    Modal.confirm({
      title: "确认全量替换数据库？",
      icon: <WarningOutlined />,
      content: (
        <div>
          <p>
            上传的 SQLite 将<strong>完全替换</strong>当前库中的全部数据（企业、进度、用户等）。
          </p>
          <p>系统会先自动备份当前库到 data/backups/，然后替换。</p>
          <p style={{ marginBottom: 0 }}>
            此操作不可撤销（仅能从备份恢复）。完成后可能需要刷新页面或重新登录。
          </p>
        </div>
      ),
      okText: "确认替换",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        setDbLoading(true);
        setDbResult(null);
        try {
          const result = await importDb(dbFile);
          setDbResult(result);
          message.success("数据库已替换");
        } catch (e) {
          message.error(errMsg(e));
        } finally {
          setDbLoading(false);
        }
      },
    });
  };

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Typography.Title level={4} style={{ margin: 0 }}>
        数据导入
      </Typography.Title>

      <Alert
        type="success"
        showIcon
        message="下载导入模板"
        description={
          <div>
            <p style={{ marginBottom: 8 }}>
              模板含「说明」「企业档案」「任务进度」示例行，指导如何录入
              <strong>新建企业</strong>与<strong>已有企业的进度更新</strong>
              。填好后用下方 Excel 导入（建议先试跑）。
            </p>
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              loading={tplLoading}
              onClick={onDownloadTemplate}
            >
              下载导入模板
            </Button>
          </div>
        }
      />

      <Divider style={{ margin: "8px 0" }} />

      <Typography.Title level={5} style={{ margin: 0 }}>
        Excel 导入（企业档案 + 任务进度）
      </Typography.Title>
      <Alert
        type="warning"
        showIcon
        message="安全导入范围（MVP）"
        description={
          <div>
            <p style={{ marginBottom: 8 }}>
              仅写入与导出/模板格式一致的 <strong>企业档案</strong>、
              <strong>任务进度</strong> sheet（按 project_code /
              task_code upsert）。
            </p>
            <p style={{ marginBottom: 0 }}>
              阶段定义、任务明细、避坑指南等目录类 sheet
              <strong>不会被导入</strong>
              。请先试跑确认摘要，再关闭试跑正式写入。
            </p>
          </div>
        }
      />
      <Upload.Dragger
        accept=".xlsx,.xlsm"
        maxCount={1}
        beforeUpload={(f) => {
          setFile(f);
          setSummary(null);
          return false;
        }}
        onRemove={() => {
          setFile(null);
          setSummary(null);
        }}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽上传 .xlsx</p>
        <p className="ant-upload-hint">
          建议使用「下载导入模板」或「数据导出」生成的文件
        </p>
      </Upload.Dragger>
      <Space>
        <span>试跑（不写库）</span>
        <Switch checked={dryRun} onChange={setDryRun} />
        <Button
          type="primary"
          icon={<UploadOutlined />}
          loading={loading}
          onClick={onSubmitExcel}
          danger={!dryRun}
        >
          {dryRun ? "试跑预览" : "确认导入"}
        </Button>
      </Space>
      {summary && (
        <Alert
          type={summary.errors.length ? "error" : "success"}
          showIcon
          message={summary.dry_run ? "试跑摘要" : "导入摘要"}
          description={
            <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
              <li>新建企业：{summary.projects_created}</li>
              <li>更新企业：{summary.projects_updated}</li>
              <li>进度写入/更新：{summary.progress_upserted}</li>
              <li>进度跳过：{summary.progress_skipped}</li>
              {summary.warnings.slice(0, 10).map((w) => (
                <li key={w}>警告：{w}</li>
              ))}
              {summary.warnings.length > 10 && (
                <li>…另有 {summary.warnings.length - 10} 条警告</li>
              )}
            </ul>
          }
        />
      )}

      {isAdmin && (
        <>
          <Divider style={{ margin: "8px 0" }} />

          <Typography.Title level={5} style={{ margin: 0 }}>
            SQLite 全量导入（.db）
          </Typography.Title>
          <Alert
            type="error"
            showIcon
            message="危险操作：将替换当前全部数据（仅管理员）"
            description={
              <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
                <li>上传的 .db 会完全覆盖当前库（含用户与进度）</li>
                <li>替换前会自动备份到 data/backups/</li>
                <li>完成后请刷新页面；若会话失效请重新登录</li>
              </ul>
            }
          />
          <Upload.Dragger
            accept=".db"
            maxCount={1}
            beforeUpload={(f) => {
              setDbFile(f);
              setDbResult(null);
              setDbAck(false);
              return false;
            }}
            onRemove={() => {
              setDbFile(null);
              setDbResult(null);
              setDbAck(false);
            }}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽上传 .db</p>
            <p className="ant-upload-hint">须为本系统导出的 SQLite 快照</p>
          </Upload.Dragger>
          <Checkbox checked={dbAck} onChange={(e) => setDbAck(e.target.checked)}>
            我理解此操作将全量替换当前数据库，且无法一键撤销
          </Checkbox>
          <Button
            danger
            type="primary"
            icon={<UploadOutlined />}
            loading={dbLoading}
            disabled={!dbFile || !dbAck}
            onClick={onSubmitDb}
          >
            确认全量替换数据库
          </Button>
          {dbResult && (
            <Alert
              type="success"
              showIcon
              message="替换完成"
              description={
                <div>
                  <p>{dbResult.message}</p>
                  <p style={{ marginBottom: 0 }}>备份路径：{dbResult.backup_path}</p>
                </div>
              }
            />
          )}
        </>
      )}
    </Space>
  );
}
