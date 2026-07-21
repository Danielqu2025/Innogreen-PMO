import axios from "axios";

const TOKEN_KEY = "pmo_api_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export const api = axios.create({
  baseURL: "",
  timeout: 15000,
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      clearToken();
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  },
);

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
