#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Innogreen PMO 数据库初始化脚本（幂等）
用法:
  python scripts/init_db.py
  python scripts/init_db.py --db-path data/innogreen_pmo.db
  python scripts/init_db.py --excel path/to.xlsx
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DB_DIR = ROOT / "data"
DB_PATH = DB_DIR / "innogreen_pmo.db"
SQL_DIR = ROOT / "sql"

USE_EMOJI = sys.platform != "win32"


def log(msg: str, emoji: str = "") -> None:
    if USE_EMOJI and emoji:
        print(f"{emoji} {msg}")
    else:
        print(msg)


def pd_ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def load_import_excel():
    """Load import_excel.py without requiring package import."""
    path = Path(__file__).parent / "import_excel.py"
    spec = importlib.util.spec_from_file_location("import_excel", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def backup_db(db_path: Path) -> Path | None:
    if not db_path.exists():
        return None
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{db_path.stem}_backup_{pd_ts()}.db"
    # Also copy WAL/SHM if present
    for suffix in ("", "-wal", "-shm"):
        src = Path(str(db_path) + suffix) if suffix else db_path
        if src.exists():
            dst = Path(str(backup_path) + suffix) if suffix else backup_path
            shutil.copy2(src, dst)
    log(f"Backup to: {backup_path}")
    return backup_path


def remove_db_files(db_path: Path) -> None:
    """Remove db + WAL sidecars for a clean rebuild."""
    for p in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if p.exists():
            p.unlink()


def exec_sql_file(cursor: sqlite3.Cursor, path: Path, required: bool = True) -> bool:
    if not path.exists():
        if required:
            log(f"Missing required SQL: {path}")
            return False
        log(f"Skip missing: {path.name}")
        return True
    with open(path, "r", encoding="utf-8") as f:
        cursor.executescript(f.read())
    return True


def init_database(db_path: str | None = None, excel_path: str | None = None) -> bool:
    db_path = Path(db_path) if db_path else DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    log(f"Database path: {db_path}")

    # 幂等：先备份再清空重建
    backup_db(db_path)
    remove_db_files(db_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA foreign_keys=ON;")
        cursor = conn.cursor()

        log("Creating tables...")
        if not exec_sql_file(cursor, SQL_DIR / "schema.sql", required=True):
            return False
        log("7 tables created")

        log("Creating audit_log table...")
        exec_sql_file(cursor, SQL_DIR / "audit_log.sql", required=False)
        log("Audit log table created")

        log("Creating users table...")
        exec_sql_file(cursor, SQL_DIR / "users.sql", required=False)
        log("Users table created")

        log("Creating progress_journal table...")
        exec_sql_file(cursor, SQL_DIR / "progress_journal.sql", required=False)
        log("Progress journal table created")

        # 旧库升级：task_detail.is_active（schema.sql 已含该列时跳过）
        cols = [r[1] for r in cursor.execute("PRAGMA table_info(task_detail)")]
        if "is_active" not in cols:
            log("Adding task_detail.is_active...")
            cursor.execute(
                "ALTER TABLE task_detail ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
            )

        pcols = [r[1] for r in cursor.execute("PRAGMA table_info(project_progress)")]
        for col in ("planned_start", "planned_end", "vendor"):
            if col not in pcols:
                log(f"Adding project_progress.{col}...")
                cursor.execute(f"ALTER TABLE project_progress ADD COLUMN {col} TEXT")

        log("Creating indexes...")
        exec_sql_file(cursor, SQL_DIR / "indexes.sql", required=False)
        log("Indexes created")

        log("Creating triggers...")
        exec_sql_file(cursor, SQL_DIR / "triggers.sql", required=False)
        log("Triggers created")

        log("Importing seed data...")
        if not exec_sql_file(cursor, SQL_DIR / "seed.sql", required=True):
            return False
        log("Seed data imported")

        log("Importing sample data...")
        if not exec_sql_file(cursor, SQL_DIR / "sample_data.sql", required=True):
            return False
        log("Sample data imported")

        conn.commit()

        # 校验
        log("\nPhase A Data Verification:")
        checks = [
            ("stages", "stage_map", 10),
            ("tasks", "task_detail", 108),
            ("dependencies", "task_dependency", None),
            ("pitfalls", "pitfall_guide", 4),
            ("projects", "project_profile", 3),
            ("progress", "project_progress", None),
        ]
        ok = True
        for name, table, expect in checks:
            count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if expect is None:
                status = "PASS" if count > 0 else "FAIL"
            else:
                status = "PASS" if count == expect else "FAIL"
            if status == "FAIL":
                ok = False
            log(f"  [{status}] {name}: {count}" + (f" (expect {expect})" if expect else ""))

        # project_code / blockers
        codes = cursor.execute(
            "SELECT project_code FROM project_profile ORDER BY project_id"
        ).fetchall()
        log(f"  project_codes: {[r[0] for r in codes]}")
        blockers = cursor.execute(
            "SELECT COUNT(*) FROM project_progress WHERE status='卡点'"
        ).fetchone()[0]
        log(f"  blockers: {blockers}")
        self_loops = cursor.execute(
            "SELECT COUNT(*) FROM task_dependency WHERE task_id=depends_on"
        ).fetchone()[0]
        log(f"  dep_self_loops: {self_loops}")

        if not ok or blockers < 1 or self_loops != 0:
            log("Verification FAILED")
            return False

        log("\nDatabase initialization complete!")
    finally:
        conn.close()

    if excel_path:
        log(f"\nImporting from Excel: {excel_path}")
        mod = load_import_excel()
        mod.import_from_excel(str(db_path), excel_path)

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize Innogreen PMO Database")
    parser.add_argument("--db-path", default=None, help="Database path")
    parser.add_argument("--excel", default=None, help="Optional Excel import after seed")
    args = parser.parse_args()
    success = init_database(args.db_path, args.excel)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
