"""认证与用户管理路由 - Phase C

- POST /api/auth/login   账号密码登录（写会话 cookie）
- POST /api/auth/logout  登出（清会话）
- GET  /api/auth/me      当前用户（前端 AuthContext 探测）
- 管理员专用：GET/POST /api/auth/users、PATCH /api/auth/users/{id}
- 管理员专用：GET /api/auth/audit（审计 / 登录记录）
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from deps import ROLES, AdminUser, CurrentUser
from models import AuditLog, User
from rate_limit import limiter
from schemas import (
    AuditLogOut,
    ChangePasswordIn,
    LoginIn,
    UserCreate,
    UserOut,
    UserUpdate,
)
from security import hash_password, verify_password
from services.audit import (
    log_login,
    log_user_create,
    log_user_update,
    log_action,
)

router = APIRouter(prefix="/api/auth")

# 统一登录失败响应（用户不存在/密码错/已禁用 都走这条，防用户名枚举）
_LOGIN_FAIL = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    detail={"error": True, "code": "ERR_UNAUTHORIZED", "message": "用户名或密码错误"},
)


def _err(code: int, msg: str, biz: str) -> HTTPException:
    return HTTPException(code, detail={"error": True, "code": biz, "message": msg})


def _user_out(u: User) -> UserOut:
    return UserOut(
        user_id=u.user_id,
        username=u.username,
        display_name=u.display_name,
        role=u.role,
        is_active=bool(u.is_active),
        created_at=u.created_at,
    )


def _user_snapshot(u: User) -> dict:
    return {
        "username": u.username,
        "display_name": u.display_name,
        "role": u.role,
        "is_active": bool(u.is_active),
    }


@router.post("/login", response_model=UserOut)
@limiter.limit("10/minute")  # 防登录爆破；登录失败统一 401 防枚举，再加 IP 限速兜底
def login(
    request: Request,
    response: Response,
    body: LoginIn,
    db: Session = Depends(get_db),
) -> UserOut:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    user = db.execute(
        select(User).where(User.username == body.username)
    ).scalar_one_or_none()
    # 用户不存在/密码错/已禁用 → 统一 401（审计不区分原因，防枚举）
    if (
        user is None
        or not verify_password(body.password, user.password_hash)
        or user.is_active != 1
    ):
        log_login(
            db,
            body.username.strip() or "?",
            success=False,
            ip_address=ip,
            user_agent=ua,
        )
        db.commit()
        raise _LOGIN_FAIL
    request.session.clear()  # 签名 cookie 无服务端 ID 可轮换，clear 即防会话固定
    request.session["user_id"] = user.user_id
    log_login(
        db,
        user.username,
        success=True,
        user_id=user.user_id,
        ip_address=ip,
        user_agent=ua,
    )
    db.commit()
    return _user_out(user)


@router.post("/logout")
def logout(request: Request) -> dict:
    request.session.clear()
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return _user_out(user)


@router.post("/change-password", status_code=200)
@limiter.limit("10/hour")  # 防暴力改密（旧密码错误尝试）
def change_password(
    request: Request,
    response: Response,
    body: ChangePasswordIn,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    """自助改密：要求传旧密码验证身份。

    与 admin 重置密码（PATCH /users/{id}）的区别：admin 改密不需要旧密码（特权操作），
    本端点是登录用户自己改，必须先验证旧密码。失败原因分开（防枚举）。
    """
    if not verify_password(body.current_password, user.password_hash):
        log_action(
            db,
            user.username,
            "CHANGE_PASSWORD",
            "users",
            user.user_id,
            payload={"result": "fail", "reason": "wrong_current_password"},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
        raise _err(401, "当前密码错误", "ERR_UNAUTHORIZED")

    if body.current_password == body.new_password:
        raise _err(400, "新密码不能与当前密码相同", "ERR_BAD_REQUEST")

    try:
        user.password_hash = hash_password(body.new_password)
    except ValueError as e:
        raise _err(400, str(e), "ERR_BAD_REQUEST") from e
    user.updated_at = datetime.now().isoformat()

    log_action(
        db,
        user.username,
        "CHANGE_PASSWORD",
        "users",
        user.user_id,
        payload={"result": "success"},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return {"ok": True}


@router.get("/users", response_model=list[UserOut])
def list_users(
    _admin: AdminUser,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
) -> list[UserOut]:
    q = select(User)
    if not include_inactive:
        q = q.where(User.is_active == 1)
    q = q.order_by(User.user_id)
    return [_user_out(u) for u in db.execute(q).scalars().all()]


@router.post("/users", response_model=UserOut, status_code=201)
@limiter.limit("10/hour")  # 防批量建账号
def create_user(
    request: Request,
    response: Response,
    body: UserCreate,
    admin: AdminUser,
    db: Session = Depends(get_db),
) -> UserOut:
    if body.role not in ROLES:
        raise _err(400, f"无效角色: {body.role}", "ERR_BAD_REQUEST")

    username = body.username.strip()
    display_name = (body.display_name or username).strip() or None

    try:
        password_hash = hash_password(body.password)
    except ValueError as e:
        raise _err(400, str(e), "ERR_BAD_REQUEST") from e

    user = User(
        username=username,
        password_hash=password_hash,
        display_name=display_name,
        role=body.role,
        is_active=1,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise _err(409, f"用户名已存在: {username}", "ERR_CONFLICT") from e

    log_user_create(
        db,
        admin.username,
        user.user_id,
        {"username": username, "display_name": display_name, "role": body.role},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    current: AdminUser,
    request: Request,
    db: Session = Depends(get_db),
) -> UserOut:
    target = db.get(User, user_id)
    if target is None:
        raise _err(404, "用户不存在", "ERR_NOT_FOUND")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise _err(400, "未提供更新字段", "ERR_BAD_REQUEST")

    if "role" in updates and updates["role"] not in ROLES:
        raise _err(400, f"无效角色: {updates['role']}", "ERR_BAD_REQUEST")

    # 计算变更后的目标状态，用于守卫判断
    new_is_active = 1 if updates.get("is_active", bool(target.is_active)) else 0
    new_role = updates.get("role", target.role)
    was_active_admin = target.role == "admin" and target.is_active == 1
    will_remain_active_admin = new_role == "admin" and new_is_active == 1

    # 守卫1：不能禁用/降级自己（防自锁）
    if current.user_id == user_id:
        if "is_active" in updates and new_is_active == 0:
            raise _err(409, "不能禁用自己的账号", "ERR_CONFLICT")
        if "role" in updates and new_role != "admin":
            raise _err(409, "不能降低自己的管理员角色", "ERR_CONFLICT")

    # 守卫2：不能让活跃 admin 归零（保留至少一个启用管理员）
    if was_active_admin and not will_remain_active_admin:
        active_admins = db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == "admin", User.is_active == 1)
        ) or 0
        if active_admins <= 1:
            raise _err(409, "系统至少需保留一个启用的管理员", "ERR_CONFLICT")

    before = _user_snapshot(target)

    # 应用变更
    if "display_name" in updates:
        target.display_name = updates["display_name"]
    if "role" in updates:
        target.role = new_role
    if "is_active" in updates:
        target.is_active = new_is_active
    password_changed = False
    if updates.get("password"):
        try:
            target.password_hash = hash_password(updates["password"])
            password_changed = True
        except ValueError as e:
            raise _err(400, str(e), "ERR_BAD_REQUEST") from e

    target.updated_at = datetime.now().isoformat()
    after = _user_snapshot(target)
    if password_changed:
        after = {**after, "password_changed": True}

    log_user_update(
        db,
        current.username,
        user_id,
        before,
        after,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(target)
    return _user_out(target)


@router.get("/audit", response_model=list[AuditLogOut])
def list_audit(
    _admin: AdminUser,
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    resource: str | None = Query(None, description="按资源过滤，如 auth / users / projects"),
    action: str | None = Query(None, description="按动作过滤，如 LOGIN / CREATE / UPDATE"),
) -> list[AuditLogOut]:
    """管理员只读：审计日志 / 登录记录（resource=auth&action=LOGIN）。"""
    q = select(AuditLog)
    if resource:
        q = q.where(AuditLog.resource == resource)
    if action:
        q = q.where(AuditLog.action == action)
    q = q.order_by(AuditLog.audit_id.desc()).limit(limit)
    return list(db.execute(q).scalars().all())
