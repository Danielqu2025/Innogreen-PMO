"""认证与授权路由。

身份在 users；各应用角色在 app_memberships。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from deps import AdminUser, CurrentUser
from models import AppMembership, RegisteredApp, User
from schemas import (
    APP_ROLES,
    PORTAL_ROLES,
    AuditLogOut,
    LoginIn,
    MembershipOut,
    MembershipUpsert,
    RegisterIn,
    UserCreate,
    UserOut,
    UserUpdate,
    VerifySessionOut,
)
from services.audit import log_action

router = APIRouter(prefix="/api/auth")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_LOGIN_FAIL = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    detail={"error": True, "code": "ERR_UNAUTHORIZED", "message": "用户名或密码错误"},
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def is_weak_password(password: str) -> bool:
    weak_patterns = ["password", "123456", "qwerty", "admin", "change-me"]
    return any(p in password.lower() for p in weak_patterns)


def _client_ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


def _membership_out(m: AppMembership) -> MembershipOut:
    return MembershipOut(
        membership_id=m.membership_id,
        user_id=m.user_id,
        app_code=m.app_code,
        role=m.role,
        is_active=bool(m.is_active),
        created_at=m.created_at,
    )


def _list_memberships(db: Session, user_id: int, *, active_only: bool = False) -> list[AppMembership]:
    q = db.query(AppMembership).filter(AppMembership.user_id == user_id)
    if active_only:
        q = q.filter(AppMembership.is_active == 1)
    return q.order_by(AppMembership.app_code).all()


def _user_out(u: User, memberships: list[AppMembership] | None = None) -> UserOut:
    ms = memberships if memberships is not None else []
    return UserOut(
        user_id=u.user_id,
        username=u.username,
        display_name=u.display_name,
        role=u.role,
        is_active=bool(u.is_active),
        login_count=int(getattr(u, "login_count", 0) or 0),
        last_login_at=getattr(u, "last_login_at", None),
        created_at=u.created_at,
        memberships=[_membership_out(m) for m in ms],
    )


def _validate_app_role(app_code: str, role: str) -> None:
    allowed = APP_ROLES.get(app_code)
    if allowed is None:
        raise HTTPException(
            400,
            detail={"error": True, "code": "ERR_UNKNOWN_APP", "message": f"未知应用: {app_code}"},
        )
    if role not in allowed:
        raise HTTPException(
            400,
            detail={
                "error": True,
                "code": "ERR_INVALID_ROLE",
                "message": f"{app_code} 角色须为 {sorted(allowed)}，收到: {role}",
            },
        )


def upsert_membership(
    db: Session,
    user_id: int,
    body: MembershipUpsert,
) -> AppMembership:
    _validate_app_role(body.app_code, body.role)
    row = (
        db.query(AppMembership)
        .filter(AppMembership.user_id == user_id, AppMembership.app_code == body.app_code)
        .first()
    )
    now = datetime.now().isoformat()
    if row is None:
        row = AppMembership(
            user_id=user_id,
            app_code=body.app_code,
            role=body.role,
            is_active=1 if body.is_active else 0,
            created_at=now,
        )
        db.add(row)
    else:
        row.role = body.role
        row.is_active = 1 if body.is_active else 0
        row.updated_at = now
    db.flush()
    return row


# === 登录 / 登出 / 注册 ===

def _do_login(
    request: Request, username: str, password: str, db: Session
) -> User:
    """共用登录逻辑：校验密码 + 写 session + 审计。返回 User。"""
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        raise _LOGIN_FAIL
    if user.is_active != 1:
        raise _LOGIN_FAIL

    request.session["user_id"] = user.user_id
    request.session["username"] = user.username
    request.session["role"] = user.role

    now = datetime.now().isoformat()
    user.login_count = int(getattr(user, "login_count", 0) or 0) + 1
    user.last_login_at = now
    user.updated_at = now

    log_action(
        db, user.username, "LOGIN", "auth", user.user_id,
        payload={"ip": _client_ip(request), "login_count": user.login_count},
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=UserOut)
def login(request: Request, body: LoginIn, db: Session = Depends(get_db)) -> UserOut:
    """JSON 登录（SPA 客户端用）。"""
    user = _do_login(request, body.username, body.password, db)
    return _user_out(user, _list_memberships(db, user.user_id, active_only=True))


@router.post("/login-form")
def login_form(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    db: Session = Depends(get_db),
):
    """表单登录（浏览器原生 POST，无 JS）。

    成功 → 渲染目标页 next（避免 302 跟随导致某些移动浏览器丢 cookie）。
    失败 → 渲染错误页。

    HarmonyOS 自带浏览器在 POST + 302 跟随的 GET 请求中不发送刚 Set-Cookie
    的 Secure cookie（即使 SameSite=None）。解决方案：直接渲染目标页 HTML，
    跳过 302。Cookie 已写入响应头，浏览器会在渲染目标页后看到登录态。
    """
    # 防 open redirect：仅允许相对路径
    if not next.startswith("/") or next.startswith("//"):
        next = "/"

    try:
        _do_login(request, username, password, db)
    except HTTPException:
        html = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>登录失败 - INNOGREEN</title>
<style>body{font-family:system-ui;margin:0;padding:24px;background:#f4f5f7;color:#111}
.box{max-width:380px;margin:48px auto;background:#fff;border:1px solid #e5e7eb;
padding:28px 24px;border-radius:8px}h1{color:#b91c1c;font-size:20px;margin:0 0 12px}
p{margin:0 0 16px;color:#5b6572;font-size:14px}
a{display:inline-block;padding:10px 18px;background:#0b2b5b;color:#fff;
text-decoration:none;border-radius:6px;font-weight:600}</style></head>
<body><div class="box"><h1>登录失败</h1>
<p>用户名或密码错误，或账号已停用。</p>
<a href="/login">返回登录</a></div></body></html>"""
        return HTMLResponse(content=html, status_code=401)

    # 成功：渲染目标页 HTML（不走 302）
    # Portal 的 static 目录在 portal/static/，相对于 portal/routers/auth.py 是 ../static
    import os
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    index_path = os.path.join(static_dir, "index.html")
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return RedirectResponse(url=next, status_code=302)  # 兜底

    # 不需要 Cache-Control: no-cache，因为 cookie 是 fresh 的
    return HTMLResponse(content=content)


@router.post("/logout")
def logout(request: Request, _user: CurrentUser, db: Session = Depends(get_db)):
    username = request.session.get("username", "unknown")
    request.session.clear()
    log_action(db, username, "LOGOUT", "auth", None, ip_address=_client_ip(request))
    db.commit()
    return {"ok": True}


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    """自助注册：默认 Portal viewer，不自动授予任何应用权限（需管理员授权）。"""
    if is_weak_password(body.password):
        raise HTTPException(
            400,
            detail={"error": True, "code": "ERR_WEAK_PASSWORD", "message": "密码过于简单"},
        )

    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(
            409,
            detail={"error": True, "code": "ERR_CONFLICT", "message": "用户名已存在"},
        )

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        role="viewer",
        is_active=1,
        created_at=datetime.now().isoformat(),
    )
    db.add(user)
    log_action(
        db, body.username, "REGISTER", "users", None,
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(user)
    return _user_out(user, [])


@router.get("/me", response_model=UserOut)
def get_me(user: CurrentUser, db: Session = Depends(get_db)) -> UserOut:
    return _user_out(user, _list_memberships(db, user.user_id, active_only=True))


@router.get("/verify-session", response_model=VerifySessionOut)
def verify_session(
    request: Request,
    db: Session = Depends(get_db),
    app: str | None = Query(None, description="应用代码，如 PMO / qcc；传入则校验该应用 membership"),
):
    """跨应用验证 session（供 PMO/qcc 调用）。

    - 不传 app：仅校验 Portal 登录态，role = Portal 角色
    - 传 app：必须有该应用的有效 membership，否则 valid=false
    """
    user_id = request.session.get("user_id")
    if user_id is None:
        return VerifySessionOut(valid=False, user=None, app_code=app, role=None)

    user = db.query(User).filter(User.user_id == user_id, User.is_active == 1).first()
    if not user:
        return VerifySessionOut(valid=False, user=None, app_code=app, role=None)

    if not app:
        ms = _list_memberships(db, user.user_id, active_only=True)
        return VerifySessionOut(
            valid=True,
            user=_user_out(user, ms),
            app_code=None,
            role=user.role,
        )

    app_code = app.strip()
    membership = (
        db.query(AppMembership)
        .filter(
            AppMembership.user_id == user.user_id,
            AppMembership.app_code == app_code,
            AppMembership.is_active == 1,
        )
        .first()
    )
    if not membership:
        return VerifySessionOut(
            valid=False,
            user=_user_out(user, _list_memberships(db, user.user_id, active_only=True)),
            app_code=app_code,
            role=None,
        )

    return VerifySessionOut(
        valid=True,
        user=_user_out(user, _list_memberships(db, user.user_id, active_only=True)),
        app_code=app_code,
        role=membership.role,
    )


# === 用户管理（Portal admin） ===

@router.get("/users", response_model=list[UserOut])
def list_users(_admin: AdminUser, db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [_user_out(u, _list_memberships(db, u.user_id)) for u in users]


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    body: UserCreate,
    request: Request,
    _admin: AdminUser,
    db: Session = Depends(get_db),
):
    if is_weak_password(body.password):
        raise HTTPException(
            400,
            detail={"error": True, "code": "ERR_WEAK_PASSWORD", "message": "密码过于简单"},
        )
    if body.role not in PORTAL_ROLES:
        raise HTTPException(
            400,
            detail={"error": True, "code": "ERR_INVALID_ROLE", "message": "Portal 角色须为 admin/viewer"},
        )
    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(
            409,
            detail={"error": True, "code": "ERR_CONFLICT", "message": "用户名已存在"},
        )

    new_user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        role=body.role,
        is_active=1,
        created_at=datetime.now().isoformat(),
    )
    db.add(new_user)
    db.flush()

    for m in body.memberships:
        upsert_membership(db, new_user.user_id, m)

    log_action(
        db, _admin.username, "CREATE", "users", new_user.user_id,
        payload={
            "username": body.username,
            "role": body.role,
            "memberships": [m.model_dump() for m in body.memberships],
        },
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(new_user)
    return _user_out(new_user, _list_memberships(db, new_user.user_id))


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    request: Request,
    _admin: AdminUser,
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.user_id == user_id).first()
    if not target:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "用户不存在"},
        )

    if body.display_name is not None:
        target.display_name = body.display_name
    if body.role is not None:
        if body.role not in PORTAL_ROLES:
            raise HTTPException(
                400,
                detail={"error": True, "code": "ERR_INVALID_ROLE", "message": "Portal 角色须为 admin/viewer"},
            )
        target.role = body.role
    if body.is_active is not None:
        target.is_active = 1 if body.is_active else 0
    if body.password is not None:
        if is_weak_password(body.password):
            raise HTTPException(
                400,
                detail={"error": True, "code": "ERR_WEAK_PASSWORD", "message": "密码过于简单"},
            )
        target.password_hash = hash_password(body.password)

    target.updated_at = datetime.now().isoformat()
    log_action(
        db, _admin.username, "UPDATE", "users", user_id,
        payload={
            "changed": {
                k: ("***" if k == "password" else v)
                for k, v in body.model_dump(exclude_none=True).items()
            }
        },
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(target)
    return _user_out(target, _list_memberships(db, user_id))


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    request: Request,
    _admin: AdminUser,
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.user_id == user_id).first()
    if not target:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "用户不存在"},
        )
    if target.role == "admin":
        admin_count = (
            db.query(User).filter(User.role == "admin", User.is_active == 1).count()
        )
        if admin_count <= 1:
            raise HTTPException(
                400,
                detail={"error": True, "code": "ERR_LAST_ADMIN", "message": "不能删除最后一个管理员"},
            )

    target.is_active = 0
    target.updated_at = datetime.now().isoformat()
    log_action(
        db, _admin.username, "DELETE", "users", user_id,
        payload={"username": target.username},
        ip_address=_client_ip(request),
    )
    db.commit()


# === 应用授权（membership） ===

@router.get("/users/{user_id}/memberships", response_model=list[MembershipOut])
def list_user_memberships(user_id: int, _admin: AdminUser, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "用户不存在"},
        )
    return [_membership_out(m) for m in _list_memberships(db, user_id)]


@router.put("/users/{user_id}/memberships", response_model=MembershipOut)
def put_membership(
    user_id: int,
    body: MembershipUpsert,
    request: Request,
    _admin: AdminUser,
    db: Session = Depends(get_db),
):
    """授予或更新某用户在某应用的角色。"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "用户不存在"},
        )
    # 应用须已注册
    app = (
        db.query(RegisteredApp)
        .filter(RegisteredApp.app_code == body.app_code, RegisteredApp.is_active == 1)
        .first()
    )
    if not app and body.app_code not in APP_ROLES:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": f"应用不存在: {body.app_code}"},
        )

    row = upsert_membership(db, user_id, body)
    log_action(
        db, _admin.username, "UPSERT", "app_memberships", row.membership_id,
        payload={"user_id": user_id, **body.model_dump()},
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(row)
    return _membership_out(row)


@router.delete("/users/{user_id}/memberships/{app_code}", status_code=204)
def revoke_membership(
    user_id: int,
    app_code: str,
    request: Request,
    _admin: AdminUser,
    db: Session = Depends(get_db),
):
    """回收某应用授权（软禁用）。"""
    row = (
        db.query(AppMembership)
        .filter(AppMembership.user_id == user_id, AppMembership.app_code == app_code)
        .first()
    )
    if not row:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "授权记录不存在"},
        )
    row.is_active = 0
    row.updated_at = datetime.now().isoformat()
    log_action(
        db, _admin.username, "REVOKE", "app_memberships", row.membership_id,
        payload={"user_id": user_id, "app_code": app_code},
        ip_address=_client_ip(request),
    )
    db.commit()


@router.get("/audit", response_model=list[AuditLogOut])
def list_audit_logs(_admin: AdminUser, db: Session = Depends(get_db), limit: int = 100):
    from models import AuditLog

    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        AuditLogOut(
            audit_id=log.audit_id,
            actor=log.actor,
            action=log.action,
            resource=log.resource,
            resource_id=log.resource_id,
            payload=log.payload,
            ip_address=log.ip_address,
            created_at=log.created_at or "",
        )
        for log in logs
    ]
