import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Descriptions,
  Drawer,
  Modal,
  Select,
  Space,
  Steps,
  Table,
  Tag,
  Timeline,
  Typography,
  message,
  theme,
} from "antd";
import { Link, useParams, useNavigate } from "react-router-dom";
import {
  api,
  deactivateProject,
  activateProject,
  listProjectJournal,
  listStages,
  type CriticalPath,
  type JournalEntry,
  type Progress,
  type Project,
  type QccLookupResult,
  type Stage,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";

/** 任务进度阶段筛选：全部 / 指定阶段 id */
type StageFilter = "all" | number;

const statusColor: Record<string, string> = {
  卡点: "error",
  进行中: "processing",
  已完成: "success",
  待开始: "default",
  已跳过: "warning",
};

/** 周进展：展示有记录的最近若干周 */
const JOURNAL_WEEK_WINDOW = 6;

function stepStatus(s: string): "wait" | "process" | "finish" | "error" {
  if (s === "卡点") return "error";
  if (s === "已完成") return "finish";
  if (s === "进行中") return "process";
  return "wait";
}

function parseTaskCode(code: string | null | undefined): number[] {
  return (code ?? "")
    .split(".")
    .filter(Boolean)
    .map((p) => {
      const n = Number(p);
      return Number.isFinite(n) ? n : 0;
    });
}

/** 从后到前：阶段号大的在前，同阶段 task_code 大的在前 */
function cmpBackToFront(
  a: { stage_id?: number | null; task_code?: string | null },
  b: { stage_id?: number | null; task_code?: string | null },
): number {
  const sa = a.stage_id ?? -1;
  const sb = b.stage_id ?? -1;
  if (sa !== sb) return sb - sa;
  const pa = parseTaskCode(a.task_code);
  const pb = parseTaskCode(b.task_code);
  const len = Math.max(pa.length, pb.length);
  for (let i = 0; i < len; i++) {
    const da = pa[i] ?? 0;
    const db = pb[i] ?? 0;
    if (da !== db) return db - da;
  }
  return 0;
}

/** 从前到后：阶段号小的在前，同阶段 task_code 小的在前 */
function cmpFrontToBack(
  a: { stage_id?: number | null; task_code?: string | null },
  b: { stage_id?: number | null; task_code?: string | null },
): number {
  return -cmpBackToFront(a, b);
}

/** 单阶段行：按 task_code 正序 */
function rowsForStage(rows: Progress[], stageId: number): Progress[] {
  return rows.filter((r) => r.stage_id === stageId).slice().sort(cmpFrontToBack);
}

/** 取有记录的最近 N 个 week_start，保留这些周的全部条目（仍按周倒序） */
function filterRecentWeeks(journals: JournalEntry[], weekCount: number): JournalEntry[] {
  const weeks: string[] = [];
  const seen = new Set<string>();
  for (const j of journals) {
    if (!seen.has(j.week_start)) {
      seen.add(j.week_start);
      weeks.push(j.week_start);
      if (weeks.length >= weekCount) break;
    }
  }
  const keep = new Set(weeks);
  return journals.filter((j) => keep.has(j.week_start));
}

/** 解析进度时间 → 2026年07月22日（关键路径等单日标注，仍用四位年） */
function formatCnDate(value?: string | null): string | null {
  if (!value) return null;
  const m = value.trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  return `${m[1]}年${m[2]}月${m[3]}日`;
}

/** 两位年 + 零填充月日：25年03月05日 */
function formatCnDateYy(y: string, mo: string, d: string): string {
  return `${y.slice(-2)}年${mo}月${d}日`;
}

/**
 * 进度表时段：
 * - 同年同月：YY年MM月DD日~DD日
 * - 同年异月：YY年MM月DD日~MM月DD日
 * - 跨年：YY年MM月DD日~YY年MM月DD日
 * 单侧有值时只显示该侧，不拼空区间。
 */
function formatDateRange(
  start?: string | null,
  end?: string | null,
): string | null {
  const s = start?.trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
  const e = end?.trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (s && e) {
    const left = formatCnDateYy(s[1], s[2], s[3]);
    if (s[1] !== e[1]) return `${left}~${formatCnDateYy(e[1], e[2], e[3])}`;
    if (s[2] !== e[2]) return `${left}~${e[2]}月${e[3]}日`;
    return `${left}~${e[3]}日`;
  }
  if (s) return formatCnDateYy(s[1], s[2], s[3]);
  if (e) return formatCnDateYy(e[1], e[2], e[3]);
  return null;
}

/** 周起始日 → 当周周一至周日（规则同 formatDateRange） */
function formatWeekRange(weekStart?: string | null): string | null {
  const m = weekStart?.trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  const start = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  if (Number.isNaN(start.getTime())) return null;
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  const pad = (n: number) => String(n).padStart(2, "0");
  return formatDateRange(
    `${m[1]}-${m[2]}-${m[3]}`,
    `${end.getFullYear()}-${pad(end.getMonth() + 1)}-${pad(end.getDate())}`,
  );
}

/** 关键任务时间标注：已完成 / 已启动 */
function criticalPathTimeLabel(n: {
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
}): string | null {
  if (n.status === "已完成") {
    const d = formatCnDate(n.completed_at) ?? formatCnDate(n.started_at);
    return d ? `${d}已完成` : "已完成";
  }
  if (n.status === "进行中" || n.status === "卡点") {
    const d = formatCnDate(n.started_at);
    return d ? `${d}已启动` : "已启动";
  }
  return null;
}

export default function ProjectDetailPage() {
  const { id } = useParams();
  const { canWrite, user } = useAuth();
  const { token } = theme.useToken();
  const navigate = useNavigate();
  const [project, setProject] = useState<Project | null>(null);
  const [progress, setProgress] = useState<Progress[]>([]);
  const [stages, setStages] = useState<Stage[]>([]);
  const [cp, setCp] = useState<CriticalPath | null>(null);
  const [journals, setJournals] = useState<JournalEntry[]>([]);
  const [qccInfo, setQccInfo] = useState<QccLookupResult | null>(null);
  const [qccDrawerOpen, setQccDrawerOpen] = useState(false);
  const [vendorQccInfo, setVendorQccInfo] = useState<QccLookupResult | null>(null);
  const [vendorDrawerOpen, setVendorDrawerOpen] = useState(false);
  const [vendorCompanyName, setVendorCompanyName] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [stageFilter, setStageFilter] = useState<StageFilter>("all");
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  const isAdmin = user?.role === "admin";

  const handleDeactivate = async () => {
    if (!id) return;
    try {
      await deactivateProject(Number(id));
      message.success("项目已停用");
      navigate("/ops/projects");
    } catch {
      message.error("停用失败");
    }
  };

  const handleActivate = async () => {
    if (!id) return;
    try {
      await activateProject(Number(id));
      message.success("项目已恢复");
      // 刷新当前页
      window.location.reload();
    } catch {
      message.error("恢复失败");
    }
  };

  /** 查询第三方单位的 qcc 信息并打开抽屉 */
  const openVendorDrawer = (vendorName: string) => {
    setVendorCompanyName(vendorName);
    api
      .get<QccLookupResult>("/api/ops/qcc/companies/lookup", {
        params: { name: vendorName },
      })
      .then((r) => {
        setVendorQccInfo(r.data);
        setVendorDrawerOpen(true);
      })
      .catch(() => {
        setVendorQccInfo({ found: false, company: null, qualifications: [], stats: null });
        setVendorDrawerOpen(true);
      });
  };

  useEffect(() => {
    if (!id) return;
    const pid = Number(id);
    Promise.all([
      api.get<Project>(`/api/ops/projects/${id}`),
      api.get<Progress[]>(`/api/ops/projects/${id}/progress`),
      api.get<CriticalPath>(`/api/ops/projects/${id}/critical-path`),
      listProjectJournal(pid, { limit: 100 }),
      listStages(),
    ])
      .then(([p, pr, c, j, s]) => {
        setProject(p.data);
        setProgress(pr.data);
        setCp(c.data);
        setJournals(j);
        setStages(s);
        // 默认：项目当前阶段；否则按 sort_order 第一个阶段；再否则「全部」
        if (p.data.current_stage_id != null) {
          setStageFilter(p.data.current_stage_id);
        } else if (s.length > 0) {
          const first = s.slice().sort((a, b) => a.sort_order - b.sort_order)[0];
          setStageFilter(first.stage_id);
        } else {
          setStageFilter("all");
        }
        // 同时尝试从 qcc 拉取企业工商信息和资质（优先用统一社会信用代码，其次用企业全称）
        const qccParams: { credit_code?: string; name?: string } = {};
        if (p.data.credit_code) {
          qccParams.credit_code = p.data.credit_code;
        } else if (p.data.full_name) {
          qccParams.name = p.data.full_name;
        }
        if (qccParams.credit_code || qccParams.name) {
          api
            .get<QccLookupResult>("/api/ops/qcc/companies/lookup", { params: qccParams })
            .then((q) => setQccInfo(q.data))
            .catch(() => {
              // qcc 未配置或查询失败，静默忽略
            });
        }
      })
      .catch((e) => setError(e.message));
  }, [id]);

  const highlight = useMemo(() => {
    if (!cp?.nodes) return [];
    return cp.nodes
      .filter((n) => ["卡点", "进行中", "已完成"].includes(n.status))
      .slice()
      .sort(cmpBackToFront);
  }, [cp]);

  const progressView = useMemo(() => {
    if (stageFilter === "all") {
      const ordered =
        stages.length > 0
          ? stages.slice().sort((a, b) => a.sort_order - b.sort_order)
          : [...new Set(progress.map((r) => r.stage_id).filter((x): x is number => x != null))]
              .sort((a, b) => a - b)
              .map((stage_id) => ({ stage_id }));
      const rows: Progress[] = [];
      for (const s of ordered) {
        rows.push(...rowsForStage(progress, s.stage_id));
      }
      return rows;
    }

    return rowsForStage(progress, stageFilter);
  }, [progress, stageFilter, stages]);

  /** 固定展示项目当前阶段，不随 Select 筛选变化 */
  const progressHint = useMemo(() => {
    const name = project?.current_stage_name;
    if (!name) return "当前阶段未设置";
    return (
      <>
        当前阶段
        <Typography.Text strong style={{ fontSize: 14, color: token.colorPrimary }}>
          「{name}」
        </Typography.Text>
      </>
    );
  }, [project?.current_stage_name, token.colorPrimary]);

  const progressEmptyText =
    stageFilter === "all" ? "暂无进度记录" : "该阶段暂无进度记录";

  const stageFilterOptions = useMemo(() => {
    const opts: { value: string; label: string }[] = [];
    const list =
      stages.length > 0
        ? stages.slice().sort((a, b) => a.sort_order - b.sort_order)
        : [];
    for (const s of list) {
      opts.push({
        value: String(s.stage_id),
        label: `${s.stage_id}. ${s.stage_name}`,
      });
    }
    opts.push({ value: "all", label: "全部" });
    return opts;
  }, [stages]);

  const journalsView = useMemo(
    () => filterRecentWeeks(journals, JOURNAL_WEEK_WINDOW),
    [journals],
  );

  const journalWeekCount = useMemo(() => {
    const s = new Set(journalsView.map((j) => j.week_start));
    return s.size;
  }, [journalsView]);

  /** 各任务最近一条周进展（journals 已按 week_start 倒序） */
  const latestJournalByTask = useMemo(() => {
    const map = new Map<number, JournalEntry>();
    for (const j of journals) {
      if (j.task_id == null) continue;
      if (!map.has(j.task_id)) map.set(j.task_id, j);
    }
    return map;
  }, [journals]);

  if (error) return <Alert type="error" message={error} />;
  if (!project) return <Typography.Text>加载中…</Typography.Text>;

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
        <Space>
          <Typography.Title level={3} style={{ margin: 0 }}>
            {project.short_name || project.project_code}
          </Typography.Title>
          {canWrite && (
            <Link to={`/ops/projects/${id}/edit`}>
              <Button size="small">编辑</Button>
            </Link>
          )}
          {qccInfo?.found && (
            <Button type="primary" size="small" onClick={() => setQccDrawerOpen(true)}>
              企业详情
            </Button>
          )}
          {isAdmin && (
            project.is_active !== 0 ? (
              <Button
                size="small"
                danger
                onClick={() => setDeleteModalOpen(true)}
              >
                停用
              </Button>
            ) : (
              <Button
                size="small"
                type="primary"
                onClick={handleActivate}
              >
                恢复
              </Button>
            )
          )}
        </Space>
        <Link to="/ops/projects">
          <Button>返回</Button>
        </Link>
      </div>
      <Descriptions bordered size="small" column={{ xs: 1, sm: 2 }}>
        <Descriptions.Item label="全称" span={2}>
          {project.full_name || "—"}
        </Descriptions.Item>
        <Descriptions.Item label="编号">{project.project_code}</Descriptions.Item>
        <Descriptions.Item label="状态">
          <Tag color={statusColor[project.project_status]}>{project.project_status}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="进度">{project.progress_percent}%</Descriptions.Item>
        <Descriptions.Item label="类型">{project.business_type}</Descriptions.Item>
        <Descriptions.Item label="楼栋">{project.building}</Descriptions.Item>
        <Descriptions.Item label="当前阶段" span={2}>
          {project.current_stage_name}
        </Descriptions.Item>
        <Descriptions.Item label="备注" span={2}>
          {project.notes}
        </Descriptions.Item>
      </Descriptions>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 16,
          marginTop: 24,
          marginBottom: 8,
          flexWrap: "wrap",
        }}
      >
        <Typography.Title level={4} style={{ margin: 0 }}>
          任务进度
          <Typography.Text type="secondary" style={{ fontSize: 14, fontWeight: 400, marginLeft: 8 }}>
            {progressHint}
          </Typography.Text>
        </Typography.Title>
        <Select
          style={{ minWidth: 200 }}
          value={stageFilter === "all" ? "all" : String(stageFilter)}
          options={stageFilterOptions}
          onChange={(v) => {
            if (v === "all") setStageFilter("all");
            else setStageFilter(Number(v));
          }}
        />
      </div>
      <Table
        rowKey="task_id"
        dataSource={progressView}
        size="small"
        scroll={{ x: canWrite ? 1130 : 1050 }}
        pagination={false}
        locale={{ emptyText: progressEmptyText }}
        columns={[
          { title: "编号", dataIndex: "task_code", width: 90 },
          {
            title: "任务",
            dataIndex: "task_name",
            width: 200,
            ellipsis: true,
          },
          {
            title: "状态",
            dataIndex: "status",
            width: 100,
            render: (s: string) => <Tag color={statusColor[s] || "default"}>{s}</Tag>,
          },
          {
            title: "计划起止",
            width: 150,
            render: (_: unknown, row: Progress) =>
              formatDateRange(row.planned_start, row.planned_end) || "—",
          },
          {
            title: "实际起止",
            width: 150,
            render: (_: unknown, row: Progress) =>
              formatDateRange(row.started_at, row.completed_at) || "—",
          },
          {
            title: "最近周进展",
            width: 220,
            render: (_: unknown, row: Progress) => {
              const j = latestJournalByTask.get(row.task_id);
              if (!j) return "—";
              const range = formatWeekRange(j.week_start) || j.week_start;
              return (
                <div>
                  <div>{range}</div>
                  <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                    {j.note}
                  </div>
                </div>
              );
            },
          },
          {
            title: "卡点说明",
            dataIndex: "blocker_note",
            width: 140,
            ellipsis: true,
          },
          {
            title: "第三方单位",
            dataIndex: "vendor",
            width: 120,
            render: (v: string | null | undefined) =>
              v ? (
                <Button type="link" size="small" onClick={() => openVendorDrawer(v)}>
                  {v}
                </Button>
              ) : null,
          },
          ...(canWrite
            ? [
                {
                  title: "操作",
                  width: 80,
                  render: (_: unknown, row: Progress) => (
                    <Link to={`/ops/projects/${id}/tasks/${row.task_id}`}>
                      <Button type="link" size="small">
                        更新
                      </Button>
                    </Link>
                  ),
                },
              ]
            : []),
        ]}
      />

      <Typography.Title level={4} style={{ marginTop: 24 }}>
        关键路径（关键任务）
      </Typography.Title>
      {highlight.length > 0 ? (
        <Steps
          direction="vertical"
          size="small"
          items={highlight.map((n) => {
            const timeLabel = criticalPathTimeLabel(n);
            const parts = [n.stage_name, timeLabel, n.blocker_note].filter(Boolean);
            return {
              title: `${n.task_code ?? ""} ${n.task_name}`,
              description: parts.join(" · ") || undefined,
              status: stepStatus(n.status),
            };
          })}
        />
      ) : (
        <Typography.Text type="secondary">暂无关键任务进度</Typography.Text>
      )}

      <Typography.Title level={4} style={{ marginTop: 24 }}>
        周进展
        {journalWeekCount > 0
          ? `（有记录的最近 ${journalWeekCount} 周）`
          : ""}
      </Typography.Title>
      {journalsView.length === 0 ? (
        <Typography.Text type="secondary">暂无周记（导入或任务页可追加）</Typography.Text>
      ) : (
        <Timeline
          items={journalsView.map((j) => ({
            children: (
              <div>
                <Typography.Text strong>
                  {j.week_start}
                  {j.week_label ? ` · ${j.week_label}` : ""}
                </Typography.Text>
                <div>
                  <Typography.Text type="secondary">
                    {j.task_code ? `${j.task_code} ${j.task_name ?? ""}` : "项目级"}
                    {j.source === "excel_import" ? " · Excel导入" : ""}
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
      <Modal
        title="确认停用"
        open={deleteModalOpen}
        onOk={handleDeactivate}
        onCancel={() => setDeleteModalOpen(false)}
        okText="确认停用"
        okButtonProps={{ danger: true }}
      >
        <p>
          确定要停用项目 <strong>{project.project_code}</strong> 吗？
        </p>
        <p style={{ color: "#888" }}>
          停用后该项目将从默认列表中隐藏，但仍可通过筛选恢复。
        </p>
      </Modal>

      {/* 企业详情抽屉（qcc 工商信息 + 资质证照） */}
      <Drawer
        title={qccInfo?.company?.name ?? "企业详情"}
        open={qccDrawerOpen}
        onClose={() => setQccDrawerOpen(false)}
        width={680}
      >
        {qccInfo?.stats && (
          <div style={{ marginBottom: 16 }}>
            <Typography.Text type="secondary">
              资质证照 {qccInfo.stats.total} 项
              {qccInfo.stats.valid > 0 && (
                <Tag color="success" style={{ marginLeft: 8 }}>
                  有效 {qccInfo.stats.valid}
                </Tag>
              )}
              {qccInfo.stats.expiring_soon > 0 && (
                <Tag color="warning" style={{ marginLeft: 4 }}>
                  即将到期 {qccInfo.stats.expiring_soon}
                </Tag>
              )}
              {qccInfo.stats.expired > 0 && (
                <Tag color="error" style={{ marginLeft: 4 }}>
                  已过期 {qccInfo.stats.expired}
                </Tag>
              )}
            </Typography.Text>
          </div>
        )}
        <Descriptions bordered size="small" column={{ xs: 1, sm: 2 }}>
          {qccInfo?.company?.credit_code && (
            <Descriptions.Item label="统一社会信用代码">
              {qccInfo.company.credit_code}
            </Descriptions.Item>
          )}
          {qccInfo?.company?.legal_person && (
            <Descriptions.Item label="法定代表人">
              {qccInfo.company.legal_person}
            </Descriptions.Item>
          )}
          {qccInfo?.company?.status && (
            <Descriptions.Item label="登记状态">
              <Tag color={qccInfo.company.status === "存续" ? "success" : "default"}>
                {qccInfo.company.status}
              </Tag>
            </Descriptions.Item>
          )}
          {qccInfo?.company?.founded_date && (
            <Descriptions.Item label="成立日期">
              {qccInfo.company.founded_date}
            </Descriptions.Item>
          )}
          {qccInfo?.company?.registered_capital && (
            <Descriptions.Item label="注册资本">
              {qccInfo.company.registered_capital}
            </Descriptions.Item>
          )}
          {qccInfo?.company?.paid_capital && (
            <Descriptions.Item label="实缴资本">
              {qccInfo.company.paid_capital}
            </Descriptions.Item>
          )}
          {qccInfo?.company?.company_type && (
            <Descriptions.Item label="企业类型">
              {qccInfo.company.company_type}
            </Descriptions.Item>
          )}
          {qccInfo?.company?.staff_size && (
            <Descriptions.Item label="人员规模">
              {qccInfo.company.staff_size}
            </Descriptions.Item>
          )}
          {qccInfo?.company?.insured_count && (
            <Descriptions.Item label="参保人数">
              {qccInfo.company.insured_count}
            </Descriptions.Item>
          )}
          {qccInfo?.company?.industry && (
            <Descriptions.Item label="所属行业">
              {qccInfo.company.industry}
            </Descriptions.Item>
          )}
          {qccInfo?.company?.region && (
            <Descriptions.Item label="所属区域">
              {qccInfo.company.region}
            </Descriptions.Item>
          )}
          {qccInfo?.company?.registration_authority && (
            <Descriptions.Item label="登记机关">
              {qccInfo.company.registration_authority}
            </Descriptions.Item>
          )}
          {qccInfo?.company?.business_term && (
            <Descriptions.Item label="营业期限">
              {qccInfo.company.business_term}
            </Descriptions.Item>
          )}
          {qccInfo?.company?.taxpayer_qualification && (
            <Descriptions.Item label="纳税人资质">
              {qccInfo.company.taxpayer_qualification}
            </Descriptions.Item>
          )}
          <Descriptions.Item label="注册地址" span={2}>
            {qccInfo?.company?.address || "—"}
          </Descriptions.Item>
          {qccInfo?.company?.business_scope && (
            <Descriptions.Item label="经营范围" span={2}>
              <div style={{ maxHeight: 150, overflowY: "auto", whiteSpace: "pre-wrap" }}>
                {qccInfo.company.business_scope}
              </div>
            </Descriptions.Item>
          )}
          {qccInfo?.company?.qcc_synced_at && (
            <Descriptions.Item label="数据同步时间">
              {qccInfo.company.qcc_synced_at}
            </Descriptions.Item>
          )}
        </Descriptions>

        {/* 资质证照列表 */}
        {qccInfo?.qualifications && qccInfo.qualifications.length > 0 && (
          <>
            <Typography.Title level={5} style={{ marginTop: 24, marginBottom: 12 }}>
              资质证照
            </Typography.Title>
            <Table
              rowKey="id"
              dataSource={qccInfo.qualifications}
              size="small"
              pagination={{ pageSize: 10, size: "small" }}
              scroll={{ x: 900 }}
              columns={[
                {
                  title: "资质名称",
                  dataIndex: "name",
                  width: 220,
                  ellipsis: true,
                },
                {
                  title: "证书编号",
                  dataIndex: "cert_no",
                  width: 160,
                  ellipsis: true,
                },
                { title: "类别", dataIndex: "category", width: 100 },
                {
                  title: "等级",
                  dataIndex: "level",
                  width: 70,
                  render: (v: string | null) => v || "—",
                },
                {
                  title: "有效期至",
                  dataIndex: "valid_to",
                  width: 120,
                  render: (v: string | null) => {
                    if (!v) return "长期";
                    const now = new Date();
                    const exp = new Date(v);
                    const diffDays = Math.ceil(
                      (exp.getTime() - now.getTime()) / (1000 * 60 * 60 * 24),
                    );
                    if (diffDays < 0)
                      return <Tag color="error">{v}（已过期）</Tag>;
                    if (diffDays <= 30)
                      return <Tag color="warning">{v}（即将到期）</Tag>;
                    return v;
                  },
                },
                {
                  title: "发证机关",
                  dataIndex: "issuer",
                  width: 160,
                  ellipsis: true,
                },
              ]}
            />
          </>
        )}
      </Drawer>

      {/* 第三方单位详情抽屉 */}
      <Drawer
        title={vendorCompanyName || "第三方单位"}
        open={vendorDrawerOpen}
        onClose={() => setVendorDrawerOpen(false)}
        width={600}
      >
        {vendorQccInfo?.found && vendorQccInfo.company ? (
          <>
            <Descriptions bordered size="small" column={{ xs: 1, sm: 2 }}>
              {vendorQccInfo.company.credit_code && (
                <Descriptions.Item label="统一社会信用代码">
                  {vendorQccInfo.company.credit_code}
                </Descriptions.Item>
              )}
              {vendorQccInfo.company.legal_person && (
                <Descriptions.Item label="法定代表人">
                  {vendorQccInfo.company.legal_person}
                </Descriptions.Item>
              )}
              {vendorQccInfo.company.status && (
                <Descriptions.Item label="登记状态">
                  <Tag color={vendorQccInfo.company.status === "存续" ? "success" : "default"}>
                    {vendorQccInfo.company.status}
                  </Tag>
                </Descriptions.Item>
              )}
              {vendorQccInfo.company.registered_capital && (
                <Descriptions.Item label="注册资本">
                  {vendorQccInfo.company.registered_capital}
                </Descriptions.Item>
              )}
              {vendorQccInfo.company.industry && (
                <Descriptions.Item label="所属行业">
                  {vendorQccInfo.company.industry}
                </Descriptions.Item>
              )}
              <Descriptions.Item label="注册地址" span={2}>
                {vendorQccInfo.company.address || "—"}
              </Descriptions.Item>
              {vendorQccInfo.company.business_scope && (
                <Descriptions.Item label="经营范围" span={2}>
                  <div style={{ maxHeight: 150, overflowY: "auto", whiteSpace: "pre-wrap" }}>
                    {vendorQccInfo.company.business_scope}
                  </div>
                </Descriptions.Item>
              )}
            </Descriptions>
            {vendorQccInfo.qualifications && vendorQccInfo.qualifications.length > 0 && (
              <>
                <Typography.Title level={5} style={{ marginTop: 20, marginBottom: 8 }}>
                  资质证照
                </Typography.Title>
                <Table
                  rowKey="id"
                  dataSource={vendorQccInfo.qualifications}
                  size="small"
                  pagination={{ pageSize: 5, size: "small" }}
                  scroll={{ x: 800 }}
                  columns={[
                    { title: "资质名称", dataIndex: "name", width: 180, ellipsis: true },
                    { title: "证书编号", dataIndex: "cert_no", width: 140, ellipsis: true },
                    { title: "类别", dataIndex: "category", width: 90 },
                    {
                      title: "有效期至",
                      dataIndex: "valid_to",
                      width: 120,
                      render: (v: string | null) => {
                        if (!v) return "长期";
                        const now = new Date();
                        const exp = new Date(v);
                        const diffDays = Math.ceil(
                          (exp.getTime() - now.getTime()) / (1000 * 60 * 60 * 24),
                        );
                        if (diffDays < 0) return <Tag color="error">{v}（已过期）</Tag>;
                        if (diffDays <= 30) return <Tag color="warning">{v}（即将到期）</Tag>;
                        return v;
                      },
                    },
                    { title: "发证机关", dataIndex: "issuer", width: 140, ellipsis: true },
                  ]}
                />
              </>
            )}
          </>
        ) : (
          <Typography.Text type="secondary">
            暂无企业详情数据
          </Typography.Text>
        )}
      </Drawer>
    </div>
  );
}
