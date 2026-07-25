"""认证依赖"""
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from models import User

ROLES = ("admin", "viewer")  # Portal 自身角色；业务应用角色见 app_memberships


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """从签名 session cookie 获取用户。未登录/禁用均返回 401。"""
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
    return user


def require_role(*roles: str):
    """角色门禁工厂"""
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={"error": True, "code": "ERR_FORBIDDEN", "message": "权限不足"},
            )
        return user
    return _dep


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_role("admin"))]
# Portal 写操作仅 admin（用户/应用授权管理）
WriteUser = AdminUser
