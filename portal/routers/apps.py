"""应用管理路由"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from deps import AdminUser, CurrentUser
from models import AppMembership, AppVisibility, RegisteredApp
from schemas import AppCreate, AppOut
from services.audit import log_action

router = APIRouter(prefix="/api/apps")


def _app_out(app: RegisteredApp, my_role: str | None = None) -> AppOut:
    return AppOut(
        app_id=app.app_id,
        app_code=app.app_code,
        app_name=app.app_name,
        base_url=app.base_url,
        description=app.description,
        icon=app.icon,
        is_active=bool(app.is_active),
        created_at=app.created_at,
        my_role=my_role,
    )


def _client_ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


@router.get("", response_model=list[AppOut])
def list_apps(db: Session = Depends(get_db)):
    """列出所有已激活的应用（公开目录）。"""
    apps = (
        db.query(RegisteredApp)
        .filter(RegisteredApp.is_active == 1)
        .order_by(RegisteredApp.app_code)
        .all()
    )
    return [_app_out(a) for a in apps]


def _visible_codes(db: Session) -> set[str]:
    """应用中心可见的 app code 集合。

    规则：
    - 显式在 app_visibility 里 is_visible=0 → 隐藏
    - 显式在 app_visibility 里 is_visible=1 → 可见
    - 没有 app_visibility 行 → 默认可见（即只显式隐藏）

    返回 RegisteredApp 里 is_active=1 且不在显式隐藏列表中的 app code。
    """
    hidden_codes = {
        r.app_code
        for r in db.query(AppVisibility).filter(AppVisibility.is_visible == 0).all()
    }
    active_codes = {
        r.app_code
        for r in db.query(RegisteredApp).filter(RegisteredApp.is_active == 1).all()
    }
    return active_codes - hidden_codes


@router.get("/mine", response_model=list[AppOut])
def list_my_apps(user: CurrentUser, db: Session = Depends(get_db)):
    """当前用户有权访问的应用（按有效 membership 过滤 + 应用中心可见性过滤）。"""
    visible = _visible_codes(db)
    q = (
        db.query(RegisteredApp, AppMembership)
        .join(
            AppMembership,
            AppMembership.app_code == RegisteredApp.app_code,
        )
        .filter(
            RegisteredApp.is_active == 1,
            AppMembership.user_id == user.user_id,
            AppMembership.is_active == 1,
        )
    )
    if visible:
        q = q.filter(RegisteredApp.app_code.in_(visible))
    else:
        # 管理员把全部应用都隐藏了——返回空（避免误显示用户无权访问的）
        return []
    rows = q.order_by(RegisteredApp.app_code).all()
    return [_app_out(app, my_role=m.role) for app, m in rows]


@router.post("", response_model=AppOut, status_code=201)
def create_app(
    body: AppCreate,
    request: Request,
    _admin: AdminUser,
    db: Session = Depends(get_db),
):
    existing = (
        db.query(RegisteredApp).filter(RegisteredApp.app_code == body.app_code).first()
    )
    if existing:
        raise HTTPException(
            409,
            detail={"error": True, "code": "ERR_CONFLICT", "message": "应用代码已存在"},
        )

    app = RegisteredApp(
        app_code=body.app_code,
        app_name=body.app_name,
        base_url=body.base_url,
        description=body.description,
        icon=body.icon,
        is_active=1,
        created_at=datetime.now().isoformat(),
    )
    db.add(app)
    log_action(
        db, _admin.username, "CREATE", "apps", None,
        payload={"app_code": body.app_code, "app_name": body.app_name},
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(app)
    return _app_out(app)


@router.delete("/{app_id}", status_code=204)
def delete_app(
    app_id: int,
    request: Request,
    _admin: AdminUser,
    db: Session = Depends(get_db),
):
    app = db.query(RegisteredApp).filter(RegisteredApp.app_id == app_id).first()
    if not app:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "应用不存在"},
        )
    app.is_active = 0
    log_action(
        db, _admin.username, "DELETE", "apps", app_id,
        payload={"app_code": app.app_code},
        ip_address=_client_ip(request),
    )
    db.commit()


class _VisibilityOut(BaseModel):
    app_id: int
    app_code: str
    app_name: str
    base_url: str
    description: Optional[str] = None
    icon: Optional[str] = None
    is_visible: bool


@router.get("/visibility", response_model=list[_VisibilityOut])
def list_visibility(_admin: AdminUser, db: Session = Depends(get_db)):
    """所有已激活应用 + 当前应用中心可见性（admin 用）。"""
    apps = (
        db.query(RegisteredApp)
        .filter(RegisteredApp.is_active == 1)
        .order_by(RegisteredApp.app_code)
        .all()
    )
    vis = {
        r.app_code: bool(r.is_visible)
        for r in db.query(AppVisibility).all()
    }
    return [
        _VisibilityOut(
            app_id=a.app_id,
            app_code=a.app_code,
            app_name=a.app_name,
            base_url=a.base_url,
            description=a.description,
            icon=a.icon,
            is_visible=vis.get(a.app_code, True),  # 默认可见
        )
        for a in apps
    ]


class _VisibilityUpdate(BaseModel):
    is_visible: bool


@router.put("/visibility/{app_code}", response_model=_VisibilityOut)
def update_visibility(
    app_code: str,
    body: _VisibilityUpdate,
    request: Request,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    """切换单个 app 的应用中心可见性（admin）。"""
    app = (
        db.query(RegisteredApp)
        .filter(RegisteredApp.app_code == app_code, RegisteredApp.is_active == 1)
        .first()
    )
    if not app:
        raise HTTPException(
            404,
            detail={"error": True, "code": "ERR_NOT_FOUND", "message": "应用不存在"},
        )
    row = db.query(AppVisibility).filter(AppVisibility.app_code == app_code).first()
    if row is None:
        row = AppVisibility(app_code=app_code)
        db.add(row)
    row.is_visible = 1 if body.is_visible else 0
    row.updated_at = datetime.now().isoformat()
    row.updated_by = admin.username
    log_action(
        db, admin.username, "UPDATE", "app_visibility", app.app_id,
        payload={"app_code": app_code, "is_visible": body.is_visible},
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(row)
    return _VisibilityOut(
        app_id=app.app_id,
        app_code=app.app_code,
        app_name=app.app_name,
        base_url=app.base_url,
        description=app.description,
        icon=app.icon,
        is_visible=bool(row.is_visible),
    )
