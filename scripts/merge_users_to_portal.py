"""将 PMO / qcc / sh_eia 用户合并进 Portal（portal.db）。

用法：
  # 预览（不写库）
  python -m scripts.merge_users_to_portal --dry-run

  # 执行合并
  python -m scripts.merge_users_to_portal

  # 指定源库
  python -m scripts.merge_users_to_portal \\
    --pmo-db data/innogreen_pmo.db \\
    --qcc-db D:/Claude/qcc/data/qualifications.db \\
    --sh-eia-db D:/github/Scrapling/examples/sh_eia/data/auth.db

规则：
  - 身份以 username 去重；同名时保留已有 Portal 用户，仅补 membership
  - 密码哈希：新建用户按 PMO → qcc → sh_eia 优先级取第一个可用的
  - PMO 角色 → membership(app=PMO, role=原角色)
  - qcc：admin → membership(qcc, admin)；
         user/operator + is_approved=1 → membership(qcc, operator)；
         viewer → membership(qcc, viewer)；
         未审批 → 不建 membership（等同未授权）
  - sh_eia：status='active' → membership(sh_eia, 归一化角色；user→operator)；
            pending/disabled → 不建 membership（等同未授权）
  - Portal.role：任一源为 admin → portal admin，否则 viewer
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORTAL_DB = ROOT / "data" / "portal.db"
DEFAULT_PMO_DB = ROOT / "data" / "innogreen_pmo.db"
DEFAULT_QCC_DB = Path(r"D:\Claude\qcc\data\qualifications.db")
DEFAULT_SH_EIA_DB = Path(r"D:\github\Scrapling\examples\sh_eia\data\auth.db")

APP_ROLES = frozenset({"admin", "operator", "viewer"})
PMO_ROLES = APP_ROLES
QCC_ROLES = APP_ROLES
SH_EIA_ROLES = APP_ROLES


def normalize_app_role(role: str | None, *, default: str = "viewer") -> str:
    """统一三端角色；历史 qcc/sh_eia 的 user ≡ operator。"""
    r = (role or default).strip().lower()
    if r == "user":
        return "operator"
    if r not in APP_ROLES:
        return default
    return r


@dataclass
class SourceUser:
    username: str
    password_hash: str
    display_name: str | None
    is_active: bool
    source: str  # pmo | qcc | sh_eia
    pmo_role: str | None = None
    qcc_role: str | None = None
    qcc_approved: bool | None = None
    sh_eia_role: str | None = None
    sh_eia_active: bool | None = None


@dataclass
class PlanItem:
    username: str
    action: str  # create | update_memberships | skip
    portal_role: str
    memberships: list[tuple[str, str]] = field(default_factory=list)  # (app, role)
    notes: list[str] = field(default_factory=list)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def load_pmo_users(db_path: Path) -> list[SourceUser]:
    if not db_path.exists():
        print(f"[skip] PMO 库不存在: {db_path}")
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if not _table_exists(conn, "users"):
            print(f"[skip] PMO 无 users 表: {db_path}")
            return []
        rows = conn.execute(
            "SELECT username, password_hash, display_name, role, is_active FROM users"
        ).fetchall()
    finally:
        conn.close()

    out: list[SourceUser] = []
    for r in rows:
        role = normalize_app_role(r["role"], default="viewer")
        if role not in PMO_ROLES:
            role = "viewer"
        out.append(
            SourceUser(
                username=r["username"].strip(),
                password_hash=r["password_hash"],
                display_name=r["display_name"],
                is_active=bool(r["is_active"]),
                source="pmo",
                pmo_role=role,
            )
        )
    print(f"[load] PMO users: {len(out)} from {db_path}")
    return out


def load_qcc_users(db_path: Path) -> list[SourceUser]:
    if not db_path.exists():
        print(f"[skip] qcc 库不存在: {db_path}")
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if not _table_exists(conn, "users"):
            print(f"[skip] qcc 无 users 表: {db_path}")
            return []
        # qcc 列名可能是 full_name / is_approved
        cols = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
        name_col = "full_name" if "full_name" in cols else "display_name"
        has_approved = "is_approved" in cols
        sql = f"""
            SELECT username, password_hash, {name_col} AS display_name,
                   role, is_active
                   {', is_approved' if has_approved else ''}
            FROM users
        """
        rows = conn.execute(sql).fetchall()
    finally:
        conn.close()

    out: list[SourceUser] = []
    for r in rows:
        role = normalize_app_role(r["role"], default="operator")
        if role not in QCC_ROLES:
            role = "operator"
        approved = True
        if has_approved:
            approved = bool(r["is_approved"])
        out.append(
            SourceUser(
                username=r["username"].strip(),
                password_hash=r["password_hash"],
                display_name=r["display_name"],
                is_active=bool(r["is_active"]),
                source="qcc",
                qcc_role=role,
                qcc_approved=approved,
            )
        )
    print(f"[load] qcc users: {len(out)} from {db_path}")
    return out


def load_sh_eia_users(db_path: Path) -> list[SourceUser]:
    if not db_path.exists():
        print(f"[skip] sh_eia 库不存在: {db_path}")
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if not _table_exists(conn, "users"):
            print(f"[skip] sh_eia 无 users 表: {db_path}")
            return []
        rows = conn.execute(
            "SELECT username, password_hash, display_name, role, status FROM users"
        ).fetchall()
    finally:
        conn.close()

    out: list[SourceUser] = []
    for r in rows:
        role = normalize_app_role(r["role"], default="operator")
        if role not in SH_EIA_ROLES:
            role = "operator"
        active = (r["status"] or "").strip() == "active"
        out.append(
            SourceUser(
                username=r["username"].strip(),
                password_hash=r["password_hash"],
                display_name=r["display_name"],
                is_active=active,
                source="sh_eia",
                sh_eia_role=role,
                sh_eia_active=active,
            )
        )
    print(f"[load] sh_eia users: {len(out)} from {db_path}")
    return out


def merge_sources(
    pmo: list[SourceUser],
    qcc: list[SourceUser],
    sh_eia: list[SourceUser] | None = None,
) -> dict[str, SourceUser]:
    """按 username 合并源用户，附带各端角色信息。

    密码优先级：PMO > qcc > sh_eia（先出现的源保留其 hash）。
    """
    by_name: dict[str, SourceUser] = {}
    for u in pmo:
        by_name[u.username] = u
    for u in qcc:
        if u.username not in by_name:
            by_name[u.username] = u
        else:
            exist = by_name[u.username]
            exist.qcc_role = u.qcc_role
            exist.qcc_approved = u.qcc_approved
            if not exist.display_name and u.display_name:
                exist.display_name = u.display_name
            # 密码：已有 PMO hash 则保留；否则用 qcc
            if exist.source != "pmo" and u.password_hash:
                exist.password_hash = u.password_hash
            exist.is_active = exist.is_active or u.is_active
    for u in sh_eia or []:
        if u.username not in by_name:
            by_name[u.username] = u
        else:
            exist = by_name[u.username]
            exist.sh_eia_role = u.sh_eia_role
            exist.sh_eia_active = u.sh_eia_active
            if not exist.display_name and u.display_name:
                exist.display_name = u.display_name
            # 密码：仅在 PMO/qcc 都没提供时才用 sh_eia
            if exist.source == "sh_eia" and u.password_hash:
                exist.password_hash = u.password_hash
            exist.is_active = exist.is_active or u.is_active
    return by_name


def build_plan(
    merged: dict[str, SourceUser],
    portal_conn: sqlite3.Connection,
) -> list[PlanItem]:
    existing = {
        r["username"]: dict(r)
        for r in portal_conn.execute(
            "SELECT user_id, username, role, is_active FROM users"
        )
    }
    plan: list[PlanItem] = []
    for username, src in sorted(merged.items()):
        memberships: list[tuple[str, str]] = []
        notes: list[str] = []

        if src.pmo_role:
            memberships.append(("PMO", src.pmo_role))
        if src.qcc_role:
            if src.qcc_approved is False:
                notes.append("qcc 未审批 → 不授予 qcc membership")
            else:
                memberships.append(("qcc", src.qcc_role))

        if src.sh_eia_role:
            if src.sh_eia_active is False:
                notes.append("sh_eia 非 active（待审批/停用）→ 不授予 sh_eia membership")
            else:
                memberships.append(("sh_eia", src.sh_eia_role))

        portal_role = "admin" if (
            src.pmo_role == "admin"
            or src.qcc_role == "admin"
            or src.sh_eia_role == "admin"
        ) else "viewer"

        if username in existing:
            plan.append(
                PlanItem(
                    username=username,
                    action="update_memberships",
                    portal_role=existing[username]["role"],
                    memberships=memberships,
                    notes=notes + ["已存在于 Portal，仅补/更新 membership"],
                )
            )
        else:
            if not src.is_active:
                notes.append("源账号已禁用，仍创建但 is_active=0")
            plan.append(
                PlanItem(
                    username=username,
                    action="create",
                    portal_role=portal_role,
                    memberships=memberships,
                    notes=notes,
                )
            )
    return plan


def ensure_portal_schema(conn: sqlite3.Connection) -> None:
    """幂等建表（与 models.py 对齐，便于脚本独立运行）。"""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
          user_id INTEGER PRIMARY KEY,
          username TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL,
          display_name TEXT,
          role TEXT NOT NULL DEFAULT 'viewer',
          is_active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT,
          updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS registered_apps (
          app_id INTEGER PRIMARY KEY,
          app_code TEXT NOT NULL UNIQUE,
          app_name TEXT NOT NULL,
          base_url TEXT NOT NULL,
          description TEXT,
          icon TEXT,
          is_active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS app_memberships (
          membership_id INTEGER PRIMARY KEY,
          user_id INTEGER NOT NULL,
          app_code TEXT NOT NULL,
          role TEXT NOT NULL,
          is_active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT,
          updated_at TEXT,
          UNIQUE(user_id, app_code)
        );
        CREATE TABLE IF NOT EXISTS audit_log (
          audit_id INTEGER PRIMARY KEY,
          actor TEXT NOT NULL,
          action TEXT NOT NULL,
          resource TEXT NOT NULL,
          resource_id INTEGER,
          payload TEXT,
          ip_address TEXT,
          created_at TEXT
        );
        """
    )
    # 预置应用
    now = datetime.now().isoformat()
    for code, name, url, desc, icon in (
        ("PMO", "PMO", "http://localhost:5173", "项目管理办公室", "📊"),
        ("qcc", "qcc", "http://localhost:8765", "企业资质库", "🏢"),
        ("sh_eia", "sh_eia", "http://127.0.0.1:8080/", "上海环评资料检索", "🌱"),
    ):
        exists = conn.execute(
            "SELECT 1 FROM registered_apps WHERE app_code=?", (code,)
        ).fetchone()
        if not exists:
            conn.execute(
                """
                INSERT INTO registered_apps
                  (app_code, app_name, base_url, description, icon, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (code, name, url, desc, icon, now),
            )


def apply_plan(
    plan: list[PlanItem],
    merged: dict[str, SourceUser],
    conn: sqlite3.Connection,
) -> None:
    now = datetime.now().isoformat()
    for item in plan:
        src = merged[item.username]
        if item.action == "create":
            cur = conn.execute(
                """
                INSERT INTO users
                  (username, password_hash, display_name, role, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item.username,
                    src.password_hash,
                    src.display_name or item.username,
                    item.portal_role,
                    1 if src.is_active else 0,
                    now,
                ),
            )
            user_id = cur.lastrowid
        else:
            row = conn.execute(
                "SELECT user_id FROM users WHERE username=?", (item.username,)
            ).fetchone()
            user_id = row[0]

        for app_code, role in item.memberships:
            exist = conn.execute(
                "SELECT membership_id FROM app_memberships WHERE user_id=? AND app_code=?",
                (user_id, app_code),
            ).fetchone()
            if exist:
                conn.execute(
                    """
                    UPDATE app_memberships
                    SET role=?, is_active=1, updated_at=?
                    WHERE membership_id=?
                    """,
                    (role, now, exist[0]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO app_memberships
                      (user_id, app_code, role, is_active, created_at)
                    VALUES (?, ?, ?, 1, ?)
                    """,
                    (user_id, app_code, role, now),
                )

        conn.execute(
            """
            INSERT INTO audit_log (actor, action, resource, resource_id, payload, created_at)
            VALUES ('system/merge', ?, 'users', ?, ?, ?)
            """,
            (
                "MERGE_CREATE" if item.action == "create" else "MERGE_MEMBERSHIP",
                user_id,
                str({"username": item.username, "memberships": item.memberships}),
                now,
            ),
        )


def print_plan(plan: list[PlanItem]) -> None:
    print("\n=== 合并计划 ===")
    create_n = sum(1 for p in plan if p.action == "create")
    update_n = sum(1 for p in plan if p.action == "update_memberships")
    print(f"新建用户: {create_n}  更新授权: {update_n}  合计: {len(plan)}")
    print("-" * 72)
    for p in plan:
        ms = ", ".join(f"{a}:{r}" for a, r in p.memberships) or "(无应用授权)"
        print(f"  [{p.action:18}] {p.username:<16} portal={p.portal_role:<7} → {ms}")
        for n in p.notes:
            print(f"      note: {n}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="合并 PMO/qcc/sh_eia 用户到 Portal")
    parser.add_argument("--portal-db", type=Path, default=DEFAULT_PORTAL_DB)
    parser.add_argument("--pmo-db", type=Path, default=DEFAULT_PMO_DB)
    parser.add_argument("--qcc-db", type=Path, default=DEFAULT_QCC_DB)
    parser.add_argument("--sh-eia-db", type=Path, default=DEFAULT_SH_EIA_DB)
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写库")
    args = parser.parse_args(argv)

    pmo = load_pmo_users(args.pmo_db)
    qcc = load_qcc_users(args.qcc_db)
    sh_eia = load_sh_eia_users(args.sh_eia_db)
    merged = merge_sources(pmo, qcc, sh_eia)
    if not merged:
        print("无源用户可合并。")
        return 0

    args.portal_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.portal_db)
    conn.row_factory = sqlite3.Row
    try:
        ensure_portal_schema(conn)
        plan = build_plan(merged, conn)
        print_plan(plan)
        if args.dry_run:
            print("\n[dry-run] 未写入。去掉 --dry-run 执行合并。")
            return 0
        apply_plan(plan, merged, conn)
        conn.commit()
        print(f"\n[done] 已写入 {args.portal_db}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
