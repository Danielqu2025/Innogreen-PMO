from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from config import get_settings
from database import Base, engine, init_db
from models import AppVisibility, User  # noqa: F401  ← register for Base.metadata
from routers import apps, auth

settings = get_settings()


def ensure_bootstrap_admin() -> None:
    """冷启动建一号管理员，并授予 PMO/qcc 应用 admin 权限。"""
    from database import SessionLocal
    from models import AppMembership

    db = SessionLocal()
    try:
        count = db.query(func.count()).select_from(User).scalar() or 0
        if count > 0:
            return
        username = settings.portal_bootstrap_admin_username
        password = settings.portal_bootstrap_admin_password
        if not username or not password:
            print("[bootstrap] WARNING: users 表为空且未配置管理员，请配置后重启")
            return
        from passlib.context import CryptContext

        pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        now = __import__("datetime").datetime.now().isoformat()
        admin = User(
            username=username,
            password_hash=pwd_ctx.hash(password),
            display_name=username,
            role="admin",
            is_active=1,
            created_at=now,
        )
        db.add(admin)
        db.flush()
        for app_code, role in (("PMO", "admin"), ("qcc", "admin"), ("sh_eia", "admin")):
            db.add(
                AppMembership(
                    user_id=admin.user_id,
                    app_code=app_code,
                    role=role,
                    is_active=1,
                    created_at=now,
                )
            )
        db.commit()
        print(f"[bootstrap] 已创建管理员: {username}（含 PMO/qcc admin 授权）")
    finally:
        db.close()


def seed_default_apps() -> None:
    """预置应用；按 app_code 补齐缺失项，已有记录不覆盖（便于后续新增应用）。"""
    from database import SessionLocal
    from models import RegisteredApp
    db = SessionLocal()
    try:
        defaults = [
            (
                "PMO",
                "PMO",
                settings.pmo_public_url or "http://localhost:5173",
                "项目管理办公室",
                "📊",
            ),
            (
                "qcc",
                "qcc",
                settings.qcc_public_url or "http://localhost:8765",
                "企业资质库",
                "🏢",
            ),
            (
                "sh_eia",
                "sh_eia",
                settings.sh_eia_public_url or "http://127.0.0.1:8080/",
                "上海环评资料检索",
                "🌱",
            ),
        ]
        existing = {
            code for (code,) in db.query(RegisteredApp.app_code).all()
        }
        added = []
        for app_code, app_name, base_url, desc, icon in defaults:
            if app_code in existing:
                continue
            db.add(RegisteredApp(
                app_code=app_code,
                app_name=app_name,
                base_url=base_url,
                description=desc,
                icon=icon,
                is_active=1,
            ))
            added.append(app_code)
        if added:
            db.commit()
            print(f"[seed] 预置应用已添加: {', '.join(added)}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    ensure_bootstrap_admin()
    seed_default_apps()
    yield


_docs_on = True  # Portal 默认开启 docs
app = FastAPI(
    title="Innogreen IAM Portal",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if _docs_on else None,
)

# 信任 nginx / Cloudflare Tunnel 注入的 X-Forwarded-Proto，使 request.url.scheme
# 在反代后端为 https，cookie 能正确标记 Secure
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie=settings.session_cookie_name,
    # 生产 HTTPS：SameSite=None + Secure（鸿蒙等对 Lax+Secure 的 POST→302 跟进更稳）。
    # 本机 HTTP：None 无 Secure 会被现代浏览器直接丢弃，改用 Lax。
    same_site="none" if settings.https_only else "lax",
    https_only=settings.https_only,
    domain=settings.session_cookie_domain or None,
    max_age=60 * 60 * 24 * 7,  # 7 天
)

app.include_router(auth.router)
app.include_router(apps.router)


# === 静态页面 ===

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", response_class=HTMLResponse)
def portal_home():
    """Portal 首页（应用选择器）"""
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    """Portal 管理员：账号与应用授权"""
    return (STATIC_DIR / "admin.html").read_text(encoding="utf-8")


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return (STATIC_DIR / "login.html").read_text(encoding="utf-8")


@app.get("/register", response_class=HTMLResponse)
def register_page():
    return (STATIC_DIR / "register.html").read_text(encoding="utf-8")


if (STATIC_DIR).exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
def health():
    return {"status": "ok", "portal": "Innogreen IAM"}
