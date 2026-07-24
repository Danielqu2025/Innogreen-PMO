#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backup SQLite database to data/backups/（支持 --keep N 轮转）。"""
from __future__ import annotations

import argparse
import io
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "innogreen_pmo.db"
DEFAULT_KEEP = 14


def _ensure_utf8_stdout() -> None:
    """仅 CLI 入口调用；避免 import 时改写 sys.stdout 干扰 pytest。"""
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def backup_db(db_path: Path) -> Path:
    if not db_path.exists():
        raise FileNotFoundError(f"数据库不存在: {db_path}")

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


def prune_old_backups(backup_dir: Path, stem: str, keep: int) -> list[Path]:
    """保留最新 keep 个 `{stem}_backup_*.db`，按 mtime 降序；返回已删除路径。"""
    if keep < 1:
        raise ValueError(f"--keep 必须 ≥ 1，当前: {keep}")

    pattern = f"{stem}_backup_*.db"
    files = sorted(
        backup_dir.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    to_delete = files[keep:]
    for path in to_delete:
        path.unlink()
    return to_delete


def main() -> None:
    _ensure_utf8_stdout()
    parser = argparse.ArgumentParser(description="备份 Innogreen PMO 数据库")
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB),
        help="源数据库路径",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=DEFAULT_KEEP,
        help=f"成功备份后保留的最新备份数（默认 {DEFAULT_KEEP}）",
    )
    args = parser.parse_args()
    db_path = Path(args.db_path)
    if not db_path.is_absolute():
        db_path = (ROOT / db_path).resolve()

    if args.keep < 1:
        print(f"错误: --keep 必须 ≥ 1，当前: {args.keep}")
        sys.exit(2)

    try:
        out = backup_db(db_path)
    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)

    print(f"备份已保存: {out}")

    backup_dir = out.parent
    deleted = prune_old_backups(backup_dir, db_path.stem, args.keep)
    remaining = len(list(backup_dir.glob(f"{db_path.stem}_backup_*.db")))
    if deleted:
        print(f"已清理旧备份 {len(deleted)} 个，当前保留 {remaining} 个（--keep {args.keep}）")
    else:
        print(f"无需清理，当前备份 {remaining} 个（--keep {args.keep}）")

    sys.exit(0)


if __name__ == "__main__":
    main()
