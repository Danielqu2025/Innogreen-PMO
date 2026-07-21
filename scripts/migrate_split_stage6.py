"""将阶段6拆分为「试生产准备」+「试生产启动及三同时验收」，原正式投用改为阶段8。

保留 task_id；仅更新 stage_map / task_detail / task_dependency，并回写 current_stage。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "innogreen_pmo.db"
TOUCH = ("进行中", "已完成", "卡点", "已跳过")


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
          AND td.stage_id != 4
        ORDER BY sm.sort_order DESC
        LIMIT 1
        """,
        (project_id, *TOUCH),
    ).fetchone()
    return row[0] if row else None


def migrate(conn: sqlite3.Connection) -> None:
    # 已迁移则跳过
    names = {
        r[0]: r[1]
        for r in conn.execute("SELECT stage_id, stage_name FROM stage_map")
    }
    if names.get(8) == "正式投用" and names.get(6) == "试生产准备":
        print("已是新阶段地图，跳过结构迁移")
        return

    # 1) 先改名阶段7，释放「正式投用」名称，再插入阶段8
    conn.execute(
        """
        UPDATE stage_map
        SET stage_name='试生产启动及三同时验收', primary_owner='政府审批', critical_path='🔴',
            default_days=68, description='启动试生产与安全/环保/职业卫生三同时验收', sort_order=7
        WHERE stage_id=7
        """
    )
    conn.execute(
        """
        UPDATE stage_map
        SET stage_name='试生产准备', primary_owner='客户主导', critical_path='🔴',
            default_days=37, description='试生产方案编制、内部评审与安全评审', sort_order=6
        WHERE stage_id=6
        """
    )
    if 8 not in names:
        conn.execute(
            """
            INSERT INTO stage_map
              (stage_id, stage_name, primary_owner, critical_path, default_days, description, sort_order)
            VALUES (8, '正式投用', '客户主导', '🟢', 7, '正式投产投用', 8)
            """
        )

    # 2) 正式投用任务 → 阶段8 / 8.1（先改，避免与新 7.1 冲突）
    conn.execute(
        """
        UPDATE task_detail
        SET stage_id=8, task_code='8.1', seq=1
        WHERE task_id=107
        """
    )

    # 3) 原 6.1.4 / 6.2* → 阶段7
    moves = [
        (102, 7, "7.1", 1, 23),
        (103, 7, "7.2", 2, 45),
        (104, 7, "7.2.1", 3, 15),
        (105, 7, "7.2.2", 4, 20),
        (106, 7, "7.2.3", 5, 10),
    ]
    for task_id, stage_id, code, seq, days in moves:
        conn.execute(
            """
            UPDATE task_detail
            SET stage_id=?, task_code=?, seq=?, default_days=?
            WHERE task_id=?
            """,
            (stage_id, code, seq, days, task_id),
        )

    # 4) 阶段6 父任务更名与时长
    conn.execute(
        """
        UPDATE task_detail
        SET task_name='试生产准备', description='试生产方案与安全评审',
            default_days=37, seq=1
        WHERE task_id=98
        """
    )
    conn.execute("UPDATE task_detail SET seq=2 WHERE task_id=99")
    conn.execute("UPDATE task_detail SET seq=3 WHERE task_id=100")
    conn.execute("UPDATE task_detail SET seq=4 WHERE task_id=101")

    # 5) 依赖：父任务 6.1 改为依赖 6.1.3
    conn.execute(
        "DELETE FROM task_dependency WHERE task_id=98 AND depends_on=102"
    )
    exists = conn.execute(
        "SELECT 1 FROM task_dependency WHERE task_id=98 AND depends_on=101"
    ).fetchone()
    if not exists:
        conn.execute(
            "INSERT INTO task_dependency (task_id, depends_on, dependency_type) "
            "VALUES (98, 101, '安全评审后')"
        )


def reconcile_stages(conn: sqlite3.Connection) -> None:
    for p in conn.execute(
        "SELECT project_id, project_code, current_stage_id, project_status FROM project_profile"
    ):
        exp = expected_stage(conn, p["project_id"])
        blockers = conn.execute(
            """
            SELECT COUNT(*) FROM project_progress pg
            JOIN task_detail td ON td.task_id=pg.task_id
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
    conn.execute("PRAGMA foreign_keys=ON")
    print("迁移阶段地图…")
    migrate(conn)
    print("回写 current_stage…")
    reconcile_stages(conn)
    conn.commit()

    stages = list(conn.execute("SELECT stage_id, stage_name FROM stage_map ORDER BY sort_order"))
    print("\n阶段列表:")
    for s in stages:
        print(f"  {s['stage_id']}. {s['stage_name']}")
    print("\n阶段6-8任务:")
    for t in conn.execute(
        "SELECT task_id, stage_id, task_code, task_name FROM task_detail "
        "WHERE stage_id IN (6,7,8) ORDER BY stage_id, sort_order"
    ):
        print(f"  {t['task_id']:4} s{t['stage_id']} {t['task_code']:<8} {t['task_name']}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
