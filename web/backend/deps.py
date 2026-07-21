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
