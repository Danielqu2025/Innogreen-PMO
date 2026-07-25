"""应用管理路由"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db
from deps import AdminUser, CurrentUser
from models import AppMembership, RegisteredApp
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


@router.get("/mine", response_model=list[AppOut])
def list_my_apps(user: CurrentUser, db: Session = Depends(get_db)):
    """当前用户有权访问的应用（按有效 membership 过滤）。"""
    rows = (
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
        .order_by(RegisteredApp.app_code)
        .all()
    )
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
