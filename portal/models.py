from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class User(Base):
    """Portal 用户表（统一身份真源）。

    role 仅表示 Portal 自身管理权限（admin 可管用户/应用授权）；
    各业务应用的角色见 AppMembership。
    """
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, default="viewer")  # portal: admin / viewer
    is_active: Mapped[int] = mapped_column(default=1)
    login_count: Mapped[int] = mapped_column(default=0)
    last_login_at: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[str | None] = mapped_column(Text)


class RegisteredApp(Base):
    """已注册的应用"""
    __tablename__ = "registered_apps"

    app_id: Mapped[int] = mapped_column(primary_key=True)
    app_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    app_name: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[str | None] = mapped_column(Text)


class AppMembership(Base):
    """用户 × 应用授权（按应用分别角色）。

    无有效 membership = 无权进入该应用（替代 qcc 的 is_approved）。
    应用角色（PMO / qcc / sh_eia 统一）：admin / operator / viewer。
    """
    __tablename__ = "app_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "app_code", name="uq_membership_user_app"),
    )

    membership_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(nullable=False)
    app_code: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    """审计日志"""
    __tablename__ = "audit_log"

    audit_id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[int | None] = mapped_column()
    payload: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(Text)


class AppVisibility(Base):
    """应用中心可见性（管理员可配）。

    注册即默认可见；管理员可在 Portal /admin 关闭某个 app，
    使其从首页应用卡片和侧边栏快捷入口消失（用户个人 membership
    不受影响——只是工作台隐藏）。
    """
    __tablename__ = "app_visibility"

    app_code: Mapped[str] = mapped_column(String(50), primary_key=True)
    is_visible: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(Text)
