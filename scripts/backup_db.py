#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backup SQLite database to data/backups/."""
from __future__ import annotations

import argparse
import io
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "innogreen_pmo.db"


def backup_db(db_path: Path) -> Path:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{db_path.stem}_backup_{ts}.db"

    # 用 SQLite Online Backup API 取事务一致快照。
    # 不能再分别 copy .db / -wal / -shm：WAL 模式下三次 copy 之间若有写入提交，
    # 三件套内部会不一致（主页可能引用没拷到的 WAL 帧），备份即损坏。
    # backup() 读源库的一致合并视图，写出一个自包含的 .db（无 sidecar），最可移植。
    src = sqlite3.connect(str(db_path))
    src.execute("PRAGMA busy_timeout=5000")
    try:
        dst = sqlite3.connect(str(backup_path))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    return backup_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup Innogreen PMO database")
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB),
        help="Source database path",
    )
    args = parser.parse_args()
    db_path = Path(args.db_path)
    if not db_path.is_absolute():
        db_path = (ROOT / db_path).resolve()

    try:
        out = backup_db(db_path)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(f"Backup saved: {out}")
    sys.exit(0)


if __name__ == "__main__":
    main()
