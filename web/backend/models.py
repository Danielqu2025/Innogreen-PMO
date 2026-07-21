from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class StageMap(Base):
    __tablename__ = "stage_map"

    stage_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stage_name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    standard_name: Mapped[str | None] = mapped_column(Text)
    standard_check: Mapped[str] = mapped_column(Text, default="待核")
    standard_note: Mapped[str | None] = mapped_column(Text)
    primary_owner: Mapped[str] = mapped_column(Text, nullable=False)
    critical_path: Mapped[str] = mapped_column(Text, default="🟢")
    default_days: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    tasks: Mapped[list["TaskDetail"]] = relationship(back_populates="stage")


class TaskDetail(Base):
    __tablename__ = "task_detail"
    __table_args__ = (UniqueConstraint("stage_id", "task_name"),)

    task_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stage_id: Mapped[int] = mapped_column(ForeignKey("stage_map.stage_id"), nullable=False)
    task_name: Mapped[str] = mapped_column(Text, nullable=False)
    task_code: Mapped[str | None] = mapped_column(Text)
    seq: Mapped[int] = mapped_column(Integer, default=1)
    default_days: Mapped[int] = mapped_column(Integer, default=0)
    critical_path: Mapped[str] = mapped_column(Text, default="🟢")
    owner: Mapped[str] = mapped_column(Text, nullable=False)
    supervisor: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    stage: Mapped[StageMap] = relationship(back_populates="tasks")


class TaskDependency(Base):
    __tablename__ = "task_dependency"
    __table_args__ = (UniqueConstraint("task_id", "depends_on"),)

    dependency_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("task_detail.task_id"), nullable=False)
    depends_on: Mapped[int] = mapped_column(ForeignKey("task_detail.task_id"), nullable=False)
    dependency_type: Mapped[str | None] = mapped_column(Text, default="完成方可开始")


class PitfallGuide(Base):
    __tablename__ = "pitfall_guide"

    pitfall_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stage_ref: Mapped[str | None] = mapped_column(Text)
    wrong_action: Mapped[str] = mapped_column(Text, nullable=False)
    right_action: Mapped[str] = mapped_column(Text, nullable=False)
    standard_ref: Mapped[str | None] = mapped_column(Text)
    impact_level: Mapped[str] = mapped_column(Text, default="中")
    error_index: Mapped[str] = mapped_column(Text, default="中")
    trigger_condition: Mapped[str | None] = mapped_column(Text)
    remediation: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, default="通用化工合规")
    verified: Mapped[int] = mapped_column(Integer, default=0)


class StagePitfallRef(Base):
    __tablename__ = "stage_pitfall_ref"

    stage_id: Mapped[int] = mapped_column(ForeignKey("stage_map.stage_id"), primary_key=True)
    pitfall_id: Mapped[int] = mapped_column(ForeignKey("pitfall_guide.pitfall_id"), primary_key=True)
    ref_type: Mapped[str | None] = mapped_column(Text, default="常见")


class ProjectProfile(Base):
    __tablename__ = "project_profile"

    project_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    company_name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    short_name: Mapped[str | None] = mapped_column(Text)
    business_type: Mapped[str | None] = mapped_column(Text)
    building: Mapped[str | None] = mapped_column(Text)
    floor: Mapped[str | None] = mapped_column(Text)
    area_m2: Mapped[float | None] = mapped_column()
    current_stage_id: Mapped[int | None] = mapped_column(ForeignKey("stage_map.stage_id"))
    project_status: Mapped[str] = mapped_column(Text, default="未开始")
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)

    current_stage: Mapped[StageMap | None] = relationship()
    progress_rows: Mapped[list["ProjectProgress"]] = relationship(back_populates="project")


class ProjectProgress(Base):
    __tablename__ = "project_progress"
    __table_args__ = (UniqueConstraint("project_id", "task_id"),)

    progress_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project_profile.project_id"), nullable=False)
    task_id: Mapped[int] = mapped_column(ForeignKey("task_detail.task_id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, default="待开始")
    priority: Mapped[str | None] = mapped_column(Text, default="🟢")
    assigned_to: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[str | None] = mapped_column(Text)
    blocker_note: Mapped[str | None] = mapped_column(Text)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    actual_days: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)

    project: Mapped[ProjectProfile] = relationship(back_populates="progress_rows")
    task: Mapped[TaskDetail] = relationship()


# =============================================
# v1.3 新增模型
# =============================================

class AuditLog(Base):
    """审计日志表 - Phase C"""
    __tablename__ = "audit_log"

    audit_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)


class User(Base):
    """用户表 - Phase C 鉴权（账号密码 + 三角色）"""
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="operator")
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[str | None] = mapped_column(Text)
