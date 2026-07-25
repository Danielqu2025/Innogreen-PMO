"""鉴权依赖 - Phase C（会话 cookie + 三角色）

- 本地模式（默认）：签名 cookie → 查本地 users 表
- SSO 模式（PMO_PORTAL_BASE_URL 非空）：转发 cookie 调 Portal verify-session?app=PMO
"""
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from models import User
from services import portal_auth

ROLES = ("admin", "operator", "viewer")


@dataclass
class AuthUser:
    """当前用户（本地 ORM 或 Portal SSO 统一为此结构）。"""

    user_id: int
    username: str
    display_name: str | None
    role: str
    is_active: bool = True
    created_at: str | None = None


def escape_like(value: str) -> str:
    """转义 LIKE 通配符与转义字符自身。"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _from_orm(user: User) -> AuthUser:
    return AuthUser(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        is_active=bool(user.is_active),
        created_at=user.created_at,
    )


def get_current_user(request: Request, db: Session = Depends(get_db)) -> AuthUser:
    """未登录 / 无 PMO 授权 / 已禁用 → 401。"""
    if portal_auth.portal_enabled():
        data = portal_auth.verify_session(request)
        if data is None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail={"error": True, "code": "ERR_UNAUTHORIZED", "message": "未登录"},
            )
        return AuthUser(**data)

    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"error": True, "code": "ERR_UNAUTHORIZED", "message": "未登录"},
        )
    user = db.get(User, user_id)
    if user is None or user.is_active != 1:
        request.session.clear()
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"error": True, "code": "ERR_UNAUTHORIZED", "message": "账号已禁用或不存在"},
        )
    return _from_orm(user)


def require_role(*roles: str):
    """角色门禁工厂：角色不在白名单 → 403。"""

    def _dependency(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={"error": True, "code": "ERR_FORBIDDEN", "message": "权限不足"},
            )
        return user

    return _dependency


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
WriteUser = Annotated[AuthUser, Depends(require_role("admin", "operator"))]
AdminUser = Annotated[AuthUser, Depends(require_role("admin"))]
