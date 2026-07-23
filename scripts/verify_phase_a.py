#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase A verification gate. Exit 0 = pass."""
import io
import sqlite3
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DB = Path(__file__).parent.parent / "data" / "innogreen_pmo.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute("PRAGMA foreign_keys=ON")

issues = []

def fail(msg: str) -> None:
    issues.append(msg)
    print("FAIL:", msg)

print("=== COUNTS ===")
counts = {}
for t in [
    "stage_map", "task_detail", "task_dependency", "pitfall_guide",
    "stage_pitfall_ref", "project_profile", "project_progress",
]:
    counts[t] = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"{t}: {counts[t]}")

if counts["stage_map"] != 10:
    fail(f"stages want 10 got {counts['stage_map']}")
if counts["task_detail"] != 108:
    fail(f"tasks want 108 got {counts['task_detail']}")
if counts["project_profile"] < 2:
    fail("projects < 2")
if counts["pitfall_guide"] < 4:
    fail("pitfalls < 4")

cols = [r["name"] for r in c.execute("PRAGMA table_info(project_profile)")]
if "project_code" not in cols:
    fail("missing project_code column")

print("\n=== PROJECTS ===")
for r in c.execute(
    "SELECT project_code, project_status, current_stage_id, progress_percent FROM project_profile"
):
    print(dict(r))
    if not str(r["project_code"]).startswith("ENT-"):
        fail(f"bad project_code {r['project_code']}")

print("\n=== BLOCKERS ===")
blockers = list(c.execute(
    """
    SELECT pp.project_code, pp.project_status, pp.current_stage_id,
           td.task_code, td.stage_id AS blocker_stage, td.task_name, pg.blocker_note
    FROM project_progress pg
    JOIN project_profile pp ON pp.project_id=pg.project_id
    JOIN task_detail td ON td.task_id=pg.task_id
    WHERE pg.status='卡点'
    """
))
print("count:", len(blockers))
for r in blockers:
    print(dict(r))
    if r["project_status"] != "卡点":
        fail(f"{r['project_code']} has blocker but status={r['project_status']}")
    note = r["blocker_note"] or ""
    name = r["task_name"] or ""
    if "安评" in note and "安全" not in name and "安评" not in name:
        fail(f"安评 note on wrong task {r['task_code']}")
if len(blockers) < 1:
    fail("no blockers")

print("\n=== CURRENT STAGE (auto) ===")
# 双模式（与 progress_service.resolve_current_stage_id 一致）：
# 1) 阶段5–8任一已触达 → 取最大 sort_order（可越过1/2/3空缺）
# 2) 否则线性前序钳制：阶段1未触达 → 0；排除阶段4
LINEAR = (1, 2, 5, 6, 7, 8, 9)
ADVANCED = {5, 6, 7, 8}
TOUCH = ("进行中", "已完成", "卡点", "已跳过")
sort_orders = dict(c.execute("SELECT stage_id, sort_order FROM stage_map"))
for pp in c.execute(
    "SELECT project_id, project_code, current_stage_id FROM project_profile"
):
    touched = {
        r[0]
        for r in c.execute(
            """
            SELECT td.stage_id
            FROM project_progress pg
            JOIN task_detail td ON td.task_id = pg.task_id
            WHERE pg.project_id = ?
              AND pg.status IN (?, ?, ?, ?)
              AND td.is_active = 1
              AND td.stage_id != 4
            """,
            (pp["project_id"], *TOUCH),
        )
    }
    if not touched:
        expected = None
    elif touched & ADVANCED:
        expected = max(touched, key=lambda sid: sort_orders.get(sid, -1))
    else:
        gap_idx = next((i for i, sid in enumerate(LINEAR) if sid not in touched), None)
        if gap_idx == 0:
            expected = 0
        else:
            ceiling = None
            if gap_idx is not None:
                ceiling = sort_orders.get(LINEAR[gap_idx])
            cands = []
            for sid in touched:
                so = sort_orders.get(sid)
                if so is None:
                    continue
                if ceiling is None or so < ceiling:
                    cands.append((sid, so))
            if cands:
                expected = max(cands, key=lambda x: x[1])[0]
            else:
                expected = LINEAR[gap_idx - 1] if gap_idx and gap_idx > 0 else 0
    print(
        {
            "project_id": pp["project_id"],
            "project_code": pp["project_code"],
            "current_stage_id": pp["current_stage_id"],
            "expected_stage": expected,
        }
    )
    if pp["current_stage_id"] != expected:
        fail(
            f"{pp['project_code']} stage {pp['current_stage_id']} != expected {expected}"
        )

bad = c.execute(
    """
    SELECT COUNT(*) FROM project_progress
    WHERE status!='已完成' AND completed_at IS NOT NULL AND completed_at!=''
    """
).fetchone()[0]
if bad:
    fail(f"non-completed with completed_at: {bad}")

print("\n=== PITFALL stage_ref ===")
stages = {r[0] for r in c.execute("SELECT stage_name FROM stage_map")}
for r in c.execute("SELECT pitfall_id, stage_ref FROM pitfall_guide"):
    if r["stage_ref"] not in stages:
        fail(f"pitfall#{r['pitfall_id']} stage_ref={r['stage_ref']}")
    else:
        print("ok", r["pitfall_id"], r["stage_ref"])

print("\n=== DEPS ===")
if c.execute("SELECT COUNT(*) FROM task_dependency WHERE task_id=depends_on").fetchone()[0]:
    fail("self-loops")
# parent/child: child should not depend on parent code
sus = 0
for r in c.execute(
    """
    SELECT b.task_code AS bc, a.task_code AS ac
    FROM task_dependency d
    JOIN task_detail a ON a.task_id=d.task_id
    JOIN task_detail b ON b.task_id=d.depends_on
    """
):
    bc, ac = r["bc"] or "", r["ac"] or ""
    if ac.startswith(bc + "."):
        sus += 1
        fail(f"child_depends_on_parent {bc}->{ac}")
print("child_depends_on_parent count:", sus)

# cycles
graph, nodes, color, cycles = {}, set(), {}, []
for tid, dep in c.execute("SELECT task_id, depends_on FROM task_dependency"):
    graph.setdefault(dep, []).append(tid)
    nodes.add(tid)
    nodes.add(dep)

def dfs(u):
    color[u] = 1
    for v in graph.get(u, []):
        if color.get(v, 0) == 1:
            cycles.append((u, v))
        elif color.get(v, 0) == 0:
            dfs(v)
    color[u] = 2

for n in nodes:
    if color.get(n, 0) == 0:
        dfs(n)
if cycles:
    fail(f"cycles {cycles[:5]}")
else:
    print("cycles: 0")

print("\n=== SUMMARY ===")
if issues:
    for i, m in enumerate(issues, 1):
        print(f"{i}. {m}")
    conn.close()
    sys.exit(1)
print("Phase A verification PASSED")
conn.close()
sys.exit(0)
