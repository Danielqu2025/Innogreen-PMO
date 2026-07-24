from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from starlette.middleware.sessions import SessionMiddleware

from config import get_settings
from rate_limit import setup_rate_limit
from routers.auth import router as auth_router
from routers.ops import router as ops_router
from routers.ops import tenant_router
from security_headers import SecurityHeadersMiddleware

settings = get_settings()


def ensure_task_is_active_column() -> None:
    """旧库升级：为 task_detail 补 is_active 列。"""
    from sqlalchemy import text

    from database import engine

    with engine.begin() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(task_detail)"))]
        if "is_active" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE task_detail ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
                )
            )
            print("[migrate] task_detail.is_active 已添加")


def ensure_progress_schedule_columns() -> None:
    """旧库升级：project_progress 计划日期与第三方。"""
    from sqlalchemy import text

    from database import engine

    with engine.begin() as conn:
        cols = {
            r[1] for r in conn.execute(text("PRAGMA table_info(project_progress)"))
        }
        for col, ddl in (
            ("planned_start", "ALTER TABLE project_progress ADD COLUMN planned_start TEXT"),
            ("planned_end", "ALTER TABLE project_progress ADD COLUMN planned_end TEXT"),
            ("vendor", "ALTER TABLE project_progress ADD COLUMN vendor TEXT"),
        ):
            if col not in cols:
                conn.execute(text(ddl))
                print(f"[migrate] project_progress.{col} 已添加")


def ensure_bootstrap_admin() -> None:
    """冷启动建一号管理员：users 表为空且配置了 PMO_BOOTSTRAP_ADMIN_* 时插入一个 admin。"""
    from database import SessionLocal
    from models import User
    from security import hash_password, is_weak_password

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
        # 拒绝示例/弱密码：避免冷启动后立刻被猜中（与 schemas / security 共用黑名单）
        if len(password) < 8 or is_weak_password(password):
            print(
                "[bootstrap] ERROR: PMO_BOOTSTRAP_ADMIN_PASSWORD 过弱或仍是示例值，"
                "已拒绝创建管理员。请换成 ≥8 位的强密码后重启。"
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


def ensure_audit_immutable_triggers() -> None:
    """旧库升级：装 audit_log 不可篡改触发器（Phase D）。

    新建库已由 scripts/init_db.py 在建表阶段安装，老库（v1.3 早期版本）
    在此函数里幂等补装。

    注意：SQLAlchemy 不支持多语句 DDL 执行（含 `;` 的 CREATE TRIGGER），
    故通过 engine 拿原始 sqlite3 连接、用 executescript() 一次跑完。
    """
    import sqlite3

    from config import get_settings

    sql_path = Path(__file__).resolve().parents[2] / "sql" / "audit_log_immutable.sql"
    if not sql_path.exists():
        return
    # engine 是 SQLAlchemy Engine；拿 raw connection 转为 sqlite3 才能 executescript。
    # 这里直接用 sqlite3 连接 settings.db_path：避免和 ORM 事务竞争。
    db_path = get_settings().db_path
    raw_conn = sqlite3.connect(str(db_path))
    try:
        raw_conn.executescript(sql_path.read_text(encoding="utf-8"))
        raw_conn.commit()
    finally:
        raw_conn.close()
    print("[migrate] audit_log append-only triggers ensured")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_task_is_active_column()
    ensure_progress_schedule_columns()
    ensure_audit_immutable_triggers()
    ensure_bootstrap_admin()
    yield


_docs_on = settings.pmo_enable_docs
app = FastAPI(
    title="Innogreen PMO API",
    version="1.3.0-phase-c3",
    docs_url="/docs" if _docs_on else None,
    redoc_url="/redoc" if _docs_on else None,
    openapi_url="/openapi.json" if _docs_on else None,
    lifespan=lifespan,
)

# 中间件顺序（Starlette 后 add 的在最外层 → 先处理请求）：
#   SecurityHeaders → RateLimit → CORS → SessionMiddleware
# SecurityHeaders 在最外：所有响应都带头，包括 429 / 401。
# RateLimit 在 CORS 之内：未授权 / 已超限都先走 CORS 头再加 429。
# Session 在最内：路由级 get_current_user 才能解 session。
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.pmo_session_secret,
    same_site="lax",
    https_only=settings.pmo_https_only,
    max_age=60 * 60 * 24 * 7,  # 7 天
)
# 设置 add_middleware 顺序：先 add 的在外层
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
setup_rate_limit(app)

app.include_router(auth_router)
app.include_router(ops_router)
app.include_router(tenant_router)


@app.get("/health")
def health() -> dict:
    # 不对外暴露绝对路径（信息泄露）；仅报告库文件是否存在。
    return {
        "status": "ok",
        "db_exists": settings.db_path.exists(),
    }
