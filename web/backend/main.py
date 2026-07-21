from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from starlette.middleware.sessions import SessionMiddleware

from config import get_settings
from routers.auth import router as auth_router
from routers.ops import router as ops_router
from routers.ops import tenant_router

settings = get_settings()


def ensure_bootstrap_admin() -> None:
    """冷启动建一号管理员：users 表为空且配置了 PMO_BOOTSTRAP_ADMIN_* 时插入一个 admin。"""
    from database import SessionLocal
    from models import User
    from security import hash_password

    with SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(User)) or 0
        if count > 0:
            return
        username = settings.pmo_bootstrap_admin_username
        password = settings.pmo_bootstrap_admin_password
        if not username or not password:
            print(
                "[bootstrap] WARNING: users 表为空且未配置 PMO_BOOTSTRAP_ADMIN_USERNAME/PASSWORD，"
                "将无人能登录。请在 web/.env 配置后重启。"
            )
            return
        db.add(
            User(
                username=username,
                password_hash=hash_password(password),
                display_name=username,
                role="admin",
                is_active=1,
            )
        )
        db.commit()
        print(f"[bootstrap] 已创建管理员: {username}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_bootstrap_admin()
    yield


app = FastAPI(
    title="Innogreen PMO API",
    version="1.3.0-phase-c3",
    docs_url="/docs" if settings.pmo_enable_docs else None,
    redoc_url="/redoc" if settings.pmo_enable_docs else None,
    lifespan=lifespan,
)

# SessionMiddleware 先加，CORS 后加 → CORS 为最外层（Starlette 后 add 的在最外）
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.pmo_session_secret,
    same_site="lax",
    https_only=settings.pmo_https_only,
    max_age=60 * 60 * 24 * 7,  # 7 天
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(ops_router)
app.include_router(tenant_router)


@app.get("/health")
def health() -> dict:
    db_path = Path(settings.pmo_db_path)
    if not db_path.is_absolute():
        db_path = (Path(__file__).resolve().parents[1] / settings.pmo_db_path).resolve()
    return {
        "status": "ok",
        "db_exists": db_path.exists(),
        "db_path": str(db_path),
    }
