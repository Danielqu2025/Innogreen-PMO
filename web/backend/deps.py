"""鉴权依赖 - Phase C（会话 cookie + 三角色）

- get_current_user：从签名会话 cookie 取 user_id，每请求重查 User（角色变更/禁用实时生效）。
- require_role(*roles)：角色门禁工厂。
- CurrentUser / WriteUser / AdminUser：Annotated 别名，签名处一眼可见权限，降低"忘加门禁"风险。
"""
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from models import User

ROLES = ("admin", "operator", "viewer")


def escape_like(value: str) -> str:
    """转义 LIKE 通配符与转义字符自身。

    SQLite 的 LIKE 运算符：% 匹配任意序列，_ 匹配单字符。
    用户在搜索框输入 `%` 或 `_` 会导致模糊匹配范围扩大或绕过精确匹配
    （如搜 `ENT-01_` 会同时命中 ENT-010/ENT-011...）。
    配合 SQLAlchemy 的 `.like(..., escape='\\\\')` 使用，转义符约定为反斜杠。
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """会话 cookie → User。未登录 / 用户不存在 / 已禁用均返回 401（让前端登出）。"""
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"error": True, "code": "ERR_UNAUTHORIZED", "message": "未登录"},
        )
    user = db.get(User, user_id)
    if user is None or user.is_active != 1:
        # 账号被删/被禁：清掉本地会话 + 401，前端拦截器会踢回登录页
        request.session.clear()
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"error": True, "code": "ERR_UNAUTHORIZED", "message": "账号已禁用或不存在"},
        )
    return user


def require_role(*roles: str):
    """角色门禁工厂：角色不在白名单 → 403（注意是 403，区别于 401 未登录）。"""

    def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={"error": True, "code": "ERR_FORBIDDEN", "message": "权限不足"},
            )
        return user

    return _dependency


CurrentUser = Annotated[User, Depends(get_current_user)]
WriteUser = Annotated[User, Depends(require_role("admin", "operator"))]
AdminUser = Annotated[User, Depends(require_role("admin"))]
