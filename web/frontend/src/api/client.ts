import axios from "axios";

// 会话 cookie 鉴权：withCredentials 让浏览器在跨源时也带 cookie（同源时无害）
export const api = axios.create({
  baseURL: "",
  timeout: 15000,
  withCredentials: true,
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      const url: string = err.config?.url ?? "";
      // /api/auth/me 的 401 交给 AuthContext 处理（避免初次探测时硬跳转）；登录页自身不跳
      if (!url.includes("/api/auth/me") && !window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
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

export type UserCreate = {
  username: string;
  password: string;
  display_name?: string;
  role: Role;
};

export type UserUpdate = {
  display_name?: string;
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

// ============ 业务类型 ============
export type Project = {
  project_id: number;
  project_code: string;
  company_name: string;
  short_name: string | null;
  business_type: string | null;
  building: string | null;
  current_stage_id: number | null;
  current_stage_name: string | null;
  project_status: string;
  progress_percent: number;
  notes: string | null;
};

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
  critical_path: string;
  owner: string;
  sort_order: number;
};

export type Progress = {
  progress_id: number;
  task_id: number;
  task_code: string | null;
  task_name: string | null;
  stage_id: number | null;
  status: string;
  assigned_to: string | null;
  blocker_note: string | null;
  critical_path: string | null;
};

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

export type DashboardSummary = {
  total_projects: number;
  by_status: Record<string, number>;
  by_stage: Record<string, number>;
  blockers: Blocker[];
};

export type Pitfall = {
  pitfall_id: number;
  stage_ref: string | null;
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
    stage_name: string;
    status: string;
    blocker_note: string | null;
  }>;
  edges: Array<{ from_task_id: number; to_task_id: number }>;
};
