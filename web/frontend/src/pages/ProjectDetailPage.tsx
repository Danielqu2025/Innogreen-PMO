import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Descriptions,
  Select,
  Space,
  Steps,
  Table,
  Tag,
  Timeline,
  Typography,
  theme,
} from "antd";
import { Link, useParams } from "react-router-dom";
import {
  api,
  listProjectJournal,
  listStages,
  type CriticalPath,
  type JournalEntry,
  type Progress,
  type Project,
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
  const { canWrite } = useAuth();
  const { token } = theme.useToken();
  const [project, setProject] = useState<Project | null>(null);
  const [progress, setProgress] = useState<Progress[]>([]);
  const [stages, setStages] = useState<Stage[]>([]);
  const [cp, setCp] = useState<CriticalPath | null>(null);
  const [journals, setJournals] = useState<JournalEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [stageFilter, setStageFilter] = useState<StageFilter>("all");

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
    </div>
  );
}
