from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import get_settings

settings = get_settings()

engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _connection_record) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """初始化数据库（建表，幂等）"""
    settings = get_settings()
    # 确保 data 目录存在
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _migrate_users_login_stats()


def _migrate_users_login_stats() -> None:
    """为已有 users 表补齐 login_count / last_login_at（SQLite ALTER，幂等）。"""
    with engine.begin() as conn:
        cols = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()
        }
        if "login_count" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN login_count INTEGER NOT NULL DEFAULT 0"
            )
        if "last_login_at" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN last_login_at TEXT"
            )


class Base(DeclarativeBase):
    pass
