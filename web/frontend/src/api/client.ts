import axios from "axios";

/** 部署在 /pmo/ 下时 Vite base 为 /pmo/；本地开发为 / */
const APP_BASE = (import.meta.env.BASE_URL || "/").replace(/\/$/, "");
const PORTAL_LOGIN_KEY = "pmo_portal_login_url";

function withBase(path: string): string {
  if (!path.startsWith("/")) return path;
  return `${APP_BASE}${path}` || path;
}

/** SSO 开启时跳 Portal 登录页；否则回本应用 /login */
export function loginRedirectUrl(): string {
  const portal = localStorage.getItem(PORTAL_LOGIN_KEY);
  if (portal) return portal;
  return withBase("/login");
}

export type SsoStatus = {
  enabled: boolean;
  portal_web_url: string | null;
  portal_login_url: string | null;
  portal_register_url: string | null;
};

export async function fetchSsoStatus(): Promise<SsoStatus> {
  try {
    const r = await api.get<SsoStatus>("/api/auth/sso-status");
    if (r.data.enabled && r.data.portal_login_url) {
      localStorage.setItem(PORTAL_LOGIN_KEY, r.data.portal_login_url);
    } else {
      localStorage.removeItem(PORTAL_LOGIN_KEY);
    }
    return r.data;
  } catch {
    localStorage.removeItem(PORTAL_LOGIN_KEY);
    return {
      enabled: false,
      portal_web_url: null,
      portal_login_url: null,
      portal_register_url: null,
    };
  }
}

// 会话 cookie 鉴权：withCredentials 让浏览器在跨源时也带 cookie（同源时无害）
export const api = axios.create({
  baseURL: APP_BASE || undefined,
  timeout: 15000,
  withCredentials: true,
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      const url: string = err.config?.url ?? "";
      // /api/auth/me 的 401 交给 AuthContext 处理（避免初次探测时硬跳转）；登录页自身不跳
      if (!url.includes("/api/auth/me") && !window.location.pathname.includes("/login")) {
        window.location.href = loginRedirectUrl();
      }
    }
    return Promise.reject(err);
  },
);

// ============ 鉴权 ============
export type Role = "admin" | "operator" | "viewer";

export type User = {
  user_id: number;
  username: string;
  display_name: string | null;
  role: Role;
  is_active: boolean;
  created_at?: string | null;
};

export async function login(username: string, password: string): Promise<User> {
  const r = await api.post<User>("/api/auth/login", { username, password });
  return r.data;
}

export async function logout(): Promise<void> {
  await api.post("/api/auth/logout");
}

export async function getMe(): Promise<User | null> {
  try {
    const r = await api.get<User>("/api/auth/me");
    return r.data;
  } catch (e: unknown) {
    const err = e as { response?: { status?: number } };
    if (err.response?.status === 401) return null;
    throw e;
  }
}

export async function register(
  username: string,
  password: string,
  displayName?: string,
): Promise<User> {
  const r = await api.post<User>("/api/auth/register", {
    username,
    password,
    display_name: displayName,
  });
  return r.data;
}

export type UserCreate = {
  username: string;
  password: string;
  display_name?: string;
  role: Role;
};

export type UserUpdate = {
  display_name?: string | null;
  role?: Role;
  is_active?: boolean;
  password?: string;
};

export async function listUsers(): Promise<User[]> {
  const r = await api.get<User[]>("/api/auth/users", {
    params: { include_inactive: true },
  });
  return r.data;
}

export async function createUser(body: UserCreate): Promise<User> {
  const r = await api.post<User>("/api/auth/users", body);
  return r.data;
}

export async function updateUser(id: number, body: UserUpdate): Promise<User> {
  const r = await api.patch<User>(`/api/auth/users/${id}`, body);
  return r.data;
}

export async function deleteUser(id: number): Promise<void> {
  await api.delete(`/api/auth/users/${id}`);
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  await api.post("/api/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export type AuditLog = {
  audit_id: number;
  actor: string;
  action: string;
  resource: string;
  resource_id: number | null;
  payload: string | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
};

export async function listAuditLogs(params?: {
  limit?: number;
  resource?: string;
  action?: string;
}): Promise<AuditLog[]> {
  const r = await api.get<AuditLog[]>("/api/auth/audit", { params });
  return r.data;
}

// ============ 业务类型 ============
export type Project = {
  project_id: number;
  project_code: string;
  company_name: string;
  short_name: string | null;
  full_name: string | null;
  credit_code: string | null;
  business_type: string | null;
  building: string | null;
  current_stage_id: number | null;
  current_stage_name: string | null;
  project_status: string;
  progress_percent: number;
  notes: string | null;
  is_active?: number;
};

export async function deactivateProject(id: number): Promise<Project> {
  const r = await api.post<Project>(`/api/ops/projects/${id}/deactivate`);
  return r.data;
}

export async function activateProject(id: number): Promise<Project> {
  const r = await api.post<Project>(`/api/ops/projects/${id}/activate`);
  return r.data;
}

export type Stage = {
  stage_id: number;
  stage_name: string;
  primary_owner: string;
  critical_path: string;
  default_days: number;
  description: string | null;
  sort_order: number;
  task_count: number;
};

export type Task = {
  task_id: number;
  stage_id: number;
  task_name: string;
  task_code: string | null;
  seq?: number;
  default_days?: number;
  critical_path: string;
  owner: string;
  description?: string | null;
  sort_order: number;
  is_active?: number;
};

export type TaskCreate = {
  stage_id: number;
  task_name: string;
  parent_task_id?: number | null;
  insert_before_task_id?: number | null;
  default_days?: number;
  critical_path?: string;
  owner: string;
  description?: string | null;
};

export type TaskUpdate = {
  task_name?: string;
  default_days?: number;
  critical_path?: string;
  owner?: string;
  description?: string | null;
};

export async function listStages(): Promise<Stage[]> {
  const r = await api.get<Stage[]>("/api/ops/stages");
  return r.data;
}

export async function listTasks(params?: {
  stage_id?: number;
  include_inactive?: boolean;
}): Promise<Task[]> {
  const r = await api.get<Task[]>("/api/ops/tasks", { params });
  return r.data;
}

export async function createTask(body: TaskCreate): Promise<Task> {
  const r = await api.post<Task>("/api/ops/tasks", body);
  return r.data;
}

export async function updateTask(id: number, body: TaskUpdate): Promise<Task> {
  const r = await api.patch<Task>(`/api/ops/tasks/${id}`, body);
  return r.data;
}

export async function deactivateTask(id: number): Promise<Task> {
  const r = await api.post<Task>(`/api/ops/tasks/${id}/deactivate`);
  return r.data;
}

export async function activateTask(id: number): Promise<Task> {
  const r = await api.post<Task>(`/api/ops/tasks/${id}/activate`);
  return r.data;
}

export type Progress = {
  progress_id: number;
  task_id: number;
  task_code: string | null;
  task_name: string | null;
  stage_id: number | null;
  status: string;
  assigned_to: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  planned_start?: string | null;
  planned_end?: string | null;
  vendor?: string | null;
  blocker_note: string | null;
  critical_path: string | null;
};

export type JournalEntry = {
  journal_id: number;
  project_id: number;
  task_id: number | null;
  task_code: string | null;
  task_name: string | null;
  week_start: string;
  week_label: string | null;
  note: string;
  source: string;
  actor: string | null;
  created_at: string | null;
};

export async function listProjectJournal(
  projectId: number,
  params?: { task_id?: number; limit?: number },
): Promise<JournalEntry[]> {
  const r = await api.get<JournalEntry[]>(`/api/ops/projects/${projectId}/journal`, {
    params,
  });
  return r.data;
}

export async function listTaskJournal(
  projectId: number,
  taskId: number,
  limit = 100,
): Promise<JournalEntry[]> {
  const r = await api.get<JournalEntry[]>(
    `/api/ops/projects/${projectId}/tasks/${taskId}/journal`,
    { params: { limit } },
  );
  return r.data;
}

export async function createTaskJournal(
  projectId: number,
  taskId: number,
  body: { week_start: string; note: string; week_label?: string },
): Promise<JournalEntry> {
  const r = await api.post<JournalEntry>(
    `/api/ops/projects/${projectId}/tasks/${taskId}/journal`,
    body,
  );
  return r.data;
}

export async function updateTaskJournal(
  projectId: number,
  taskId: number,
  journalId: number,
  body: { week_start?: string; note?: string; week_label?: string | null },
): Promise<JournalEntry> {
  const r = await api.patch<JournalEntry>(
    `/api/ops/projects/${projectId}/tasks/${taskId}/journal/${journalId}`,
    body,
  );
  return r.data;
}

export async function deleteTaskJournal(
  projectId: number,
  taskId: number,
  journalId: number,
): Promise<void> {
  await api.delete(`/api/ops/projects/${projectId}/tasks/${taskId}/journal/${journalId}`);
}

export type Blocker = {
  project_id: number;
  project_code: string;
  project: string;
  task_id: number;
  task_code: string | null;
  task: string;
  note: string | null;
  project_status: string;
};

export type DashboardProject = {
  project_id: number;
  project_code: string;
  company_name: string | null;
  short_name: string | null;
  building: string | null;
  current_stage_id: number | null;
  current_stage_name: string | null;
  progress_percent: number;
  project_status: string;
  flags: { blocker: boolean; delayed: boolean; stalled: boolean };
  last_journal_week: string | null;
};

export type DelayedTask = {
  project_id: number;
  project_code: string;
  project: string;
  task_id: number;
  task_code: string | null;
  task: string;
  planned_end: string;
  status: string;
  note: string | null;
};

export type DashboardSummary = {
  total_projects: number;
  by_status: Record<string, number>;
  by_stage: Record<string, number>;
  blockers: Blocker[];
  projects: DashboardProject[];
  delayed_tasks: DelayedTask[];
  counts: {
    blocker_projects: number;
    delayed_projects: number;
    stalled_projects: number;
  };
  phase_buckets: {
    access_projects: number;
    construction_projects: number;
    operation_projects: number;
  };
};

export type Pitfall = {
  pitfall_id: number;
  stage_ref: string | null;
  task_ref: string | null;
  wrong_action: string;
  right_action: string;
  standard_ref: string | null;
  impact_level: string;
  remediation: string | null;
  source: string;
};

export type PitfallDetail = Pitfall & {
  error_index: string;
  trigger_condition: string | null;
  notes: string | null;
  verified: number;
};

export type CriticalPath = {
  project_id: number;
  project_code: string;
  nodes: Array<{
    task_id: number;
    task_code: string | null;
    task_name: string;
    stage_id: number;
    stage_name: string;
    status: string;
    blocker_note: string | null;
    started_at: string | null;
    completed_at: string | null;
  }>;
  edges: Array<{ from_task_id: number; to_task_id: number }>;
};

// ============ 数据导入/导出（Excel：管理员+操作员；DB 导出/导入：仅管理员） ============
export type ExportSheetKey =
  | "stages"
  | "tasks"
  | "projects"
  | "progress"
  | "pitfalls";

export type ImportSummary = {
  dry_run: boolean;
  projects_created: number;
  projects_updated: number;
  progress_upserted: number;
  progress_skipped: number;
  pitfalls_created: number;
  pitfalls_updated: number;
  pitfalls_skipped: number;
  warnings: string[];
  errors: string[];
};

export async function downloadExportExcel(
  sheets?: ExportSheetKey[],
): Promise<void> {
  const r = await api.get("/api/ops/export/excel", {
    responseType: "blob",
    params:
      sheets && sheets.length
        ? { sheets: sheets.join(",") }
        : undefined,
  });
  const cd = r.headers["content-disposition"] as string | undefined;
  let filename = "innogreen_pmo_export.xlsx";
  const m = cd?.match(/filename="?([^";]+)"?/i);
  if (m?.[1]) filename = m[1];
  const url = URL.createObjectURL(r.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function downloadExportDb(): Promise<void> {
  const r = await api.get("/api/ops/export/db", { responseType: "blob" });
  const cd = r.headers["content-disposition"] as string | undefined;
  let filename = "innogreen_pmo.db";
  const m = cd?.match(/filename="?([^";]+)"?/i);
  if (m?.[1]) filename = m[1];
  const url = URL.createObjectURL(r.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function downloadImportTemplate(): Promise<void> {
  const r = await api.get("/api/ops/import/template.xlsx", {
    responseType: "blob",
  });
  const cd = r.headers["content-disposition"] as string | undefined;
  let filename = "innogreen_pmo_import_template.xlsx";
  const m = cd?.match(/filename="?([^";]+)"?/i);
  if (m?.[1]) filename = m[1];
  const url = URL.createObjectURL(r.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function importExcel(
  file: File,
  dryRun = true,
): Promise<ImportSummary> {
  const form = new FormData();
  form.append("file", file);
  const r = await api.post<ImportSummary>("/api/ops/import/excel", form, {
    params: { dry_run: dryRun },
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 60000,
  });
  return r.data;
}

export type DbImportResult = {
  ok: boolean;
  backup_path: string;
  message: string;
};

export async function importDb(file: File, smartMigrate = true): Promise<DbImportResult> {
  const form = new FormData();
  form.append("file", file);
  const r = await api.post<DbImportResult>("/api/ops/import/db", form, {
    params: { confirm: true, migrate: smartMigrate },
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 120000,
  });
  return r.data;
}

// ============ qcc 企业资质库集成（方案一） ============
export type QccStatus = {
  available: boolean;
};

export type QccCompanyInfo = {
  id: number;
  name: string;
  credit_code: string | null;
  legal_person: string | null;
  status: string | null;
  founded_date: string | null;
  registered_capital: string | null;
  paid_capital: string | null;
  company_type: string | null;
  business_term: string | null;
  taxpayer_qualification: string | null;
  staff_size: string | null;
  insured_count: string | null;
  industry: string | null;
  region: string | null;
  registration_authority: string | null;
  address: string | null;
  business_scope: string | null;
  english_name: string | null;
  short_name: string | null;
  notes: string | null;
  tags: string | null;
  qcc_synced_at: string | null;
};

export type QccQualification = {
  id: number;
  category: string;
  name: string;
  cert_no: string | null;
  level: string | null;
  status: string | null;
  valid_from: string | null;
  valid_to: string | null;
  issuer: string | null;
  issue_date: string | null;
  product_name: string | null;
  scope_name: string | null;
  cert_domain: string | null;
  cert_sequence: string | null;
  cert_industry: string | null;
  business_type: string | null;
  grade: string | null;
  extra_json: string | null;
  source: string;
};

export type QccQualificationStats = {
  total: number;
  valid: number;
  expiring_soon: number;
  expired: number;
};

export type QccLookupResult = {
  found: boolean;
  company: QccCompanyInfo | null;
  qualifications: QccQualification[];
  stats: QccQualificationStats | null;
};

export type QccExpiringItem = {
  id: number;
  company_id: number;
  category: string;
  name: string;
  cert_no: string | null;
  level: string | null;
  valid_from: string | null;
  valid_to: string | null;
  issuer: string | null;
  product_name: string | null;
  company_name: string;
  credit_code: string;
};

export async function getQccStatus(): Promise<QccStatus> {
  const r = await api.get<QccStatus>("/api/ops/qcc/status");
  return r.data;
}

export async function lookupQccCompany(params: {
  credit_code?: string;
  name?: string;
}): Promise<QccLookupResult> {
  const r = await api.get<QccLookupResult>("/api/ops/qcc/companies/lookup", { params });
  return r.data;
}

export async function getQccExpiringQualifications(
  days = 30,
): Promise<QccExpiringItem[]> {
  const r = await api.get<QccExpiringItem[]>("/api/ops/qcc/companies/expiring", {
    params: { days },
  });
  return r.data;
}
