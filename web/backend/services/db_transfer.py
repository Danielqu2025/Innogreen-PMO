"""SQLite DB 导出快照 / 导入替换（Online Backup API）。"""
from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from database import dispose_engine

# SQLite 文件头（16 字节）
SQLITE_HEADER = b"SQLite format 3\x00"

# 导入时至少应存在的核心表（轻量校验）
_REQUIRED_TABLES = frozenset(
    {
        "stage_map",
        "task_detail",
        "project_profile",
        "project_progress",
        "users",
    }
)

# 上传库中 audit_log 表至少需保留 50% 的行数，防止恶意用「干净库」覆盖历史审计。
_AUDIT_LOG_MIN_RETENTION_RATIO = 0.5


def _count_table_rows(conn: sqlite3.Connection, table: str) -> int:
    # table 名来自 _REQUIRED_TABLES + 内部校验，不接受用户输入；无需参数化。
    cur = conn.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
    row = cur.fetchone()
    return int(row[0]) if row else 0


def snapshot_db_bytes(db_path: Path) -> bytes:
    """事务一致快照为自包含 .db 字节（无 WAL sidecar）。"""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        src = sqlite3.connect(str(db_path))
        src.execute("PRAGMA busy_timeout=5000")
        try:
            dst = sqlite3.connect(str(tmp_path))
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)


def backup_live_db(db_path: Path) -> Path:
    """将当前库备份到同目录 backups/，返回备份路径。"""
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{db_path.stem}_backup_{ts}.db"
    data = snapshot_db_bytes(db_path)
    backup_path.write_bytes(data)
    return backup_path


def validate_sqlite_file(file_bytes: bytes) -> None:
    """校验上传内容为可用的 PMO SQLite 库。

    除校验核心表存在外，audit_log 表行数 >= 当前库的一半（保留率阈值），
    防止恶意用「干净库」覆盖历史审计日志。
    """
    if len(file_bytes) < 100 or not file_bytes.startswith(SQLITE_HEADER):
        raise ValueError("不是有效的 SQLite 数据库文件")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(file_bytes)
    try:
        conn = sqlite3.connect(str(tmp_path))
        try:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        finally:
            conn.close()
    finally:
        tmp_path.unlink(missing_ok=True)

    missing = sorted(_REQUIRED_TABLES - tables)
    if missing:
        raise ValueError("缺少必要表: " + ", ".join(missing))

    # audit_log 行数对比：以上传库的 row 数 / 当前库 row 数 < 50% → 拒绝。
    # 注意：审计本身的 trigger 禁止 DELETE，所以合规 DB 导入场景下两库行数应一致或近似；
    # 允许小幅漂移（如时间间隔的写入）但不允许"清空审计"式导入。
    if "audit_log" in tables:
        from config import get_settings  # 延迟导入避免循环

        current_path = get_settings().db_path
        if current_path.exists():
            cur = sqlite3.connect(str(current_path))
            try:
                current_rows = _count_table_rows(cur, "audit_log")
            finally:
                cur.close()
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp2:
                tmp2_path = Path(tmp2.name)
                tmp2.write(file_bytes)
            try:
                cand = sqlite3.connect(str(tmp2_path))
                try:
                    candidate_rows = _count_table_rows(cand, "audit_log")
                finally:
                    cand.close()
            finally:
                tmp2_path.unlink(missing_ok=True)

            if current_rows > 0 and candidate_rows < current_rows * _AUDIT_LOG_MIN_RETENTION_RATIO:
                raise ValueError(
                    f"上传库的 audit_log 行数 ({candidate_rows}) 不足当前库 "
                    f"({current_rows}) 的 {_AUDIT_LOG_MIN_RETENTION_RATIO:.0%}，"
                    "拒绝覆盖以保护审计完整。"
                )


def replace_live_db(db_path: Path, file_bytes: bytes) -> Path:
    """先备份当前库，再安全替换；返回自动备份路径。

    调用方应在替换前结束业务 Session。替换后会 dispose 引擎连接池。
    """
    validate_sqlite_file(file_bytes)
    backup_path = backup_live_db(db_path)

    # 先落到临时文件，再原子替换；关闭连接以免 Windows 文件锁
    dispose_engine()

    staging = db_path.with_suffix(db_path.suffix + ".importing")
    staging.write_bytes(file_bytes)

    # 去掉旧 WAL/SHM，避免与新主库混用
    for sidecar in (Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        sidecar.unlink(missing_ok=True)

    staging.replace(db_path)
    dispose_engine()
    return backup_path
