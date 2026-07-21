from pydantic import BaseModel, ConfigDict, Field


class StageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stage_id: int
    stage_name: str
    primary_owner: str
    critical_path: str
    default_days: int
    description: str | None = None
    sort_order: int
    task_count: int = 0


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: int
    stage_id: int
    task_name: str
    task_code: str | None = None
    seq: int
    default_days: int
    critical_path: str
    owner: str
    description: str | None = None
    sort_order: int


class TaskDependencyOut(BaseModel):
    task_id: int
    depends_on: int
    dependency_type: str | None = None
    task_code: str | None = None
    task_name: str | None = None
    depends_on_code: str | None = None
    depends_on_name: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: int
    project_code: str
    company_name: str
    short_name: str | None = None
    business_type: str | None = None
    building: str | None = None
    current_stage_id: int | None = None
    current_stage_name: str | None = None
    project_status: str
    progress_percent: int
    notes: str | None = None


class ProgressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    progress_id: int
    project_id: int
    task_id: int
    task_code: str | None = None
    task_name: str | None = None
    stage_id: int | None = None
    status: str
    assigned_to: str | None = None
    completed_at: str | None = None
    blocker_note: str | None = None
    critical_path: str | None = None


class BlockerOut(BaseModel):
    project_id: int
    project_code: str
    project: str
    task_id: int
    task_code: str | None = None
    task: str
    note: str | None = None
    project_status: str


class PitfallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pitfall_id: int
    stage_ref: str | None = None
    wrong_action: str
    right_action: str
    standard_ref: str | None = None
    impact_level: str
    error_index: str
    trigger_condition: str | None = None
    remediation: str | None = None
    notes: str | None = None
    source: str
    verified: int


class DashboardSummary(BaseModel):
    total_projects: int
    by_status: dict[str, int]
    by_stage: dict[str, int]
    blockers: list[BlockerOut]


class CriticalPathNode(BaseModel):
    task_id: int
    task_code: str | None = None
    task_name: str
    stage_id: int
    stage_name: str
    critical_path: str
    status: str = "待开始"
    blocker_note: str | None = None


class CriticalPathEdge(BaseModel):
    from_task_id: int
    to_task_id: int
    dependency_type: str | None = None


class CriticalPathOut(BaseModel):
    project_id: int
    project_code: str
    nodes: list[CriticalPathNode]
    edges: list[CriticalPathEdge]


class ErrorBody(BaseModel):
    error: bool = True
    code: str
    message: str


# =============================================
# Phase C 写入 Schema
# =============================================

class ProjectCreate(BaseModel):
    """创建企业档案 - Phase C"""
    project_code: str = Field(min_length=1)
    company_name: str = Field(min_length=1)
    short_name: str | None = None
    business_type: str | None = None
    building: str | None = None
    notes: str | None = None


class ProjectUpdate(BaseModel):
    """更新企业档案 - Phase C（progress_percent 仅由任务进度回写，不可手改）"""
    short_name: str | None = None
    business_type: str | None = None
    building: str | None = None
    project_status: str | None = None
    current_stage_id: int | None = None
    notes: str | None = None


class ProgressUpdate(BaseModel):
    """更新任务进度 - Phase C"""
    status: str  # 待开始 / 进行中 / 已完成 / 已跳过 / 卡点
    assigned_to: str | None = None
    blocker_note: str | None = None


class PitfallCreate(BaseModel):
    """创建避坑指南 - Phase C3"""
    stage_ref: str = Field(min_length=1)
    wrong_action: str = Field(min_length=1)
    right_action: str = Field(min_length=1)
    standard_ref: str | None = None
    impact_level: str = "中"
    trigger_condition: str | None = None
    remediation: str | None = None
    notes: str | None = None
    source: str = "运营录入"
    ref_type: str = "常见"


# =============================================
# Phase C 鉴权 Schema
# =============================================

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    display_name: str | None = None
    role: str
    is_active: bool


class LoginIn(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    """管理员新建用户 - Phase C"""
    username: str = Field(min_length=1)
    password: str = Field(min_length=8)
    display_name: str | None = None
    role: str = "operator"


class UserUpdate(BaseModel):
    """管理员编辑用户 - Phase C（全可选）"""
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None
