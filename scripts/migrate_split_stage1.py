"""将「项目准入」拆为「项目准入」+「厂房移交」，后续阶段编号顺延。

保留 task_id；更新 stage_map / task_detail(stage_id,task_code) / stage_pitfall_ref，
并按自动阶段规则回写 current_stage（排除公用工程，现为 stage_id=4）。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "innogreen_pmo.db"
TOUCH = ("进行中", "已完成", "卡点", "已跳过")
UTILITY_STAGE_ID = 4  # 公用工程（顺延后）

# 原 1.3/1.4/1.5 → 新阶段2 编码
SPLIT_CODE = {
    "1.3": "2.1",
    "1.3.1": "2.1.1",
    "1.3.2": "2.1.2",
    "1.4": "2.2",
    "1.4.1": "2.2.1",
    "1.4.2": "2.2.2",
    "1.4.3": "2.2.3",
    "1.5": "2.3",
}


def bump_code(code: str, delta: int = 1) -> str:
    parts = code.split(".")
    parts[0] = str(int(parts[0]) + delta)
    return ".".join(parts)


def expected_stage(conn: sqlite3.Connection, project_id: int) -> int | None:
    row = conn.execute(
        """
        SELECT sm.stage_id
        FROM project_progress pg
        JOIN task_detail td ON td.task_id = pg.task_id
        JOIN stage_map sm ON sm.stage_id = td.stage_id
        WHERE pg.project_id = ?
          AND pg.status IN (?, ?, ?, ?)
          AND td.is_active = 1
          AND td.stage_id != ?
        ORDER BY sm.sort_order DESC
        LIMIT 1
        """,
        (project_id, *TOUCH, UTILITY_STAGE_ID),
    ).fetchone()
    return row[0] if row else None


def already_migrated(conn: sqlite3.Connection) -> bool:
    names = {
        r[0]: r[1]
        for r in conn.execute("SELECT stage_id, stage_name FROM stage_map")
    }
    return names.get(2) == "厂房移交" and names.get(9) == "正式投用"


def migrate(conn: sqlite3.Connection) -> None:
    if already_migrated(conn):
        print("已是新阶段地图，跳过结构迁移")
        return

    old_stages = {
        r["stage_id"]: dict(r)
        for r in conn.execute("SELECT * FROM stage_map")
    }

    conn.execute("PRAGMA foreign_keys=OFF")

    # 1) 任务先挪到临时 stage_id，避免与新编号冲突
    conn.execute("UPDATE task_detail SET stage_id = stage_id + 1000")

    # 2) 重建 stage_map
    conn.execute("DELETE FROM stage_map")

    def row(sid: int, name: str, owner: str, cp: str, days: int, desc: str, order: int):
        conn.execute(
            """
            INSERT INTO stage_map
              (stage_id, stage_name, primary_owner, critical_path, default_days, description, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (sid, name, owner, cp, days, desc, order),
        )

    row(0, "初步意向", "园区协调", "🟢", 7, "客户初步意向接触", 0)
    row(1, "项目准入", "园区协调", "🔴", 12, "发展公司预准入与管委会准入评估", 1)
    row(2, "厂房移交", "客户主导", "🔴", 15, "厂房租赁合同、移交与投资信息报送", 2)

    # old 2..8 → new 3..9
    for old_sid in range(2, 9):
        s = old_stages[old_sid]
        row(
            old_sid + 1,
            s["stage_name"],
            s["primary_owner"],
            s["critical_path"],
            s["default_days"],
            s["description"],
            old_sid + 1,
        )

    # 3) 任务归位 + 改编码
    tasks = list(
        conn.execute(
            "SELECT task_id, stage_id, task_code, seq FROM task_detail ORDER BY task_id"
        )
    )
    for t in tasks:
        old_sid = t["stage_id"] - 1000
        code = t["task_code"]
        if old_sid == 0:
            new_sid, new_code, seq = 0, code, t["seq"]
        elif old_sid == 1:
            if code in SPLIT_CODE:
                new_code = SPLIT_CODE[code]
                new_sid = 2
                # seq within 厂房移交: 2.1=1, 2.1.1=2, ...
                seq_map = {
                    "2.1": 1,
                    "2.1.1": 2,
                    "2.1.2": 3,
                    "2.2": 4,
                    "2.2.1": 5,
                    "2.2.2": 6,
                    "2.2.3": 7,
                    "2.3": 8,
                }
                seq = seq_map[new_code]
            else:
                new_sid, new_code = 1, code
                seq = 1 if code == "1.1" else 2
        else:
            new_sid = old_sid + 1
            new_code = bump_code(code, 1)
            seq = t["seq"]

        conn.execute(
            "UPDATE task_detail SET stage_id=?, task_code=?, seq=? WHERE task_id=?",
            (new_sid, new_code, seq, t["task_id"]),
        )

    # 4) 避坑阶段外键顺延（原 >=2 的阶段 +1）
    conn.execute(
        "UPDATE stage_pitfall_ref SET stage_id = stage_id + 1 WHERE stage_id >= 2"
    )

    conn.execute("PRAGMA foreign_keys=ON")


def reconcile_stages(conn: sqlite3.Connection) -> None:
    for p in conn.execute(
        "SELECT project_id, project_code, current_stage_id, project_status FROM project_profile"
    ):
        exp = expected_stage(conn, p["project_id"])
        blockers = conn.execute(
            """
            SELECT COUNT(*) FROM project_progress pg
            JOIN task_detail td ON td.task_id = pg.task_id
            WHERE pg.project_id=? AND pg.status='卡点' AND td.is_active=1
            """,
            (p["project_id"],),
        ).fetchone()[0]
        new_status = p["project_status"]
        if blockers:
            new_status = "卡点"
        elif p["project_status"] == "卡点":
            new_status = "进行中"
        if p["current_stage_id"] != exp or p["project_status"] != new_status:
            conn.execute(
                "UPDATE project_profile SET current_stage_id=?, project_status=? WHERE project_id=?",
                (exp, new_status, p["project_id"]),
            )
            print(
                f"  {p['project_code']}: stage {p['current_stage_id']}→{exp}, "
                f"status {p['project_status']}→{new_status}"
            )


def main() -> int:
    if not DB.exists():
        print(f"DB not found: {DB}", file=sys.stderr)
        return 1
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    print("迁移阶段地图（拆分项目准入）…")
    migrate(conn)
    print("回写 current_stage…")
    reconcile_stages(conn)
    conn.commit()

    print("\n阶段列表:")
    for s in conn.execute(
        "SELECT stage_id, stage_name FROM stage_map ORDER BY sort_order"
    ):
        print(f"  {s['stage_id']}. {s['stage_name']}")
    print("\n阶段1-2任务:")
    for t in conn.execute(
        "SELECT task_id, stage_id, task_code, task_name FROM task_detail "
        "WHERE stage_id IN (1,2) ORDER BY stage_id, sort_order"
    ):
        print(f"  {t['task_id']:4} s{t['stage_id']} {t['task_code']:<8} {t['task_name']}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
