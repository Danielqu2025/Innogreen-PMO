from pydantic import BaseModel, Field

# 各应用允许的角色（三端统一；历史 qcc/sh_eia 的 user ≡ operator）
APP_ROLES: dict[str, frozenset[str]] = {
    "PMO": frozenset({"admin", "operator", "viewer"}),
    "qcc": frozenset({"admin", "operator", "viewer"}),
    "sh_eia": frozenset({"admin", "operator", "viewer"}),
}
PORTAL_ROLES = frozenset({"admin", "viewer"})


class MembershipOut(BaseModel):
    membership_id: int
    user_id: int
    app_code: str
    role: str
    is_active: bool
    created_at: str | None = None


class MembershipUpsert(BaseModel):
    app_code: str = Field(min_length=1)
    role: str = Field(min_length=1)
    is_active: bool = True


class UserOut(BaseModel):
    user_id: int
    username: str
    display_name: str | None = None
    role: str  # Portal 自身角色
    is_active: bool
    login_count: int = 0
    last_login_at: str | None = None
    created_at: str | None = None
    memberships: list[MembershipOut] = []


class LoginIn(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RegisterIn(BaseModel):
    username: str = Field(min_length=2)
    password: str = Field(min_length=8)
    display_name: str | None = None


class UserCreate(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=8)
    display_name: str | None = None
    role: str = "viewer"  # Portal 角色
    memberships: list[MembershipUpsert] = []


class UserUpdate(BaseModel):
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8)


class VerifySessionOut(BaseModel):
    """跨应用验证 session 的响应。

    传入 app 时：valid=true 且 role 为该应用角色；无 membership 则 valid=false。
    不传 app 时：仅校验 Portal 登录态，role 为 Portal 角色。
    """
    valid: bool
    user: UserOut | None = None
    app_code: str | None = None
    role: str | None = None


class AppOut(BaseModel):
    app_id: int
    app_code: str
    app_name: str
    base_url: str
    description: str | None = None
    icon: str | None = None
    is_active: bool = True
    created_at: str | None = None
    # 当前用户在该应用的角色（仅 /api/apps/mine 填充）
    my_role: str | None = None


class AppCreate(BaseModel):
    app_code: str = Field(min_length=1)
    app_name: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    description: str | None = None
    icon: str | None = None


class AuditLogOut(BaseModel):
    audit_id: int
    actor: str
    action: str
    resource: str
    resource_id: int | None = None
    payload: str | None = None
    ip_address: str | None = None
    created_at: str
