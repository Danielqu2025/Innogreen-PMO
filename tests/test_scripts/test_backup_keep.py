"""Unit test for backup_db.py prune_old_backups keep-N logic."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path


def _load_backup_db():
    root = Path(__file__).resolve().parents[2]
    path = root / "scripts" / "backup_db.py"
    spec = importlib.util.spec_from_file_location("backup_db", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_prune_old_backups_keeps_newest(tmp_path: Path) -> None:
    mod = _load_backup_db()
    stem = "innogreen_pmo"
    paths = []
    base = 1_700_000_000
    for i in range(5):
        p = tmp_path / f"{stem}_backup_2026010{i}_120000.db"
        p.write_bytes(b"x")
        os.utime(p, (base + i, base + i))
        paths.append(p)

    deleted = mod.prune_old_backups(tmp_path, stem, keep=3)
    assert len(deleted) == 2
    remaining = sorted(
        tmp_path.glob(f"{stem}_backup_*.db"),
        key=lambda p: p.stat().st_mtime,
    )
    assert len(remaining) == 3
    # 留下的应是 mtime 最新的 3 个
    assert remaining == paths[-3:]


def test_prune_old_backups_safe_when_fewer_than_keep(tmp_path: Path) -> None:
    mod = _load_backup_db()
    stem = "innogreen_pmo"
    for i in range(2):
        (tmp_path / f"{stem}_backup_2026010{i}_120000.db").write_bytes(b"x")

    deleted = mod.prune_old_backups(tmp_path, stem, keep=14)
    assert deleted == []
    assert len(list(tmp_path.glob(f"{stem}_backup_*.db"))) == 2
