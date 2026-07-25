from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import get_settings


class Base(DeclarativeBase):
    pass


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
    # 方案一：附加 qcc 数据库（只读），用于企业工商信息查询
    qcc_path = settings.pmo_qcc_db_path
    if qcc_path:
        import os
        if os.path.isfile(qcc_path):
            # SQLite 不支持 READONLY 关键字；只读靠应用层只查不写实现
            cursor.execute(f"ATTACH DATABASE '{qcc_path}' AS qcc")
        # 文件不存在时静默跳过，不阻断主库
    cursor.close()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def dispose_engine() -> None:
    """关闭连接池，便于替换 SQLite 文件后重新打开。"""
    engine.dispose()
