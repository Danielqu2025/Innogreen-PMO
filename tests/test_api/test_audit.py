"""审计日志落库断言（业务写 + 用户管理）。"""
import json
import sqlite3
from pathlib import Path

TEST_DB = Path(__file__).resolve().parents[2] / "data" / "test_api.db"

STAGE = "厂房改造项目前期审批准备"


def _latest_audit(resource: str | None = None) -> dict | None:
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    if resource:
        row = conn.execute(
            "SELECT * FROM audit_log WHERE resource=? ORDER BY audit_id DESC LIMIT 1",
            (resource,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM audit_log ORDER BY audit_id DESC LIMIT 1"
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def test_project_create_writes_audit(operator_client):
    r = operator_client.post(
        "/api/ops/projects",
        json={
            "project_code": "ENT-AUDIT",
            "company_name": "ENT-AUDIT",
            "business_type": "研发",
        },
    )
    assert r.status_code == 201, r.text
    pid = r.json()["project_id"]

    audit = _latest_audit("projects")
    assert audit is not None
    assert audit["action"] == "CREATE"
    assert audit["resource_id"] == pid
    assert audit["actor"] == "pytest_operator"

    conn = sqlite3.connect(TEST_DB)
    conn.execute("DELETE FROM project_profile WHERE project_id=?", (pid,))
    conn.commit()
    conn.close()


def test_progress_update_writes_audit(operator_client, ent01):
    pid = ent01["project_id"]
    r = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/18",
        json={"status": "进行中", "assigned_to": "审计测试"},
    )
    assert r.status_code == 200, r.text

    audit = _latest_audit("progress")
    assert audit is not None
    assert audit["action"] == "UPDATE"
    payload = json.loads(audit["payload"] or "{}")
    assert payload.get("project_id") == pid
    assert payload.get("task_id") == 18


def test_pitfall_create_writes_audit(operator_client):
    r = operator_client.post(
        "/api/ops/pitfalls",
        json={
            "stage_ref": STAGE,
            "wrong_action": "审计错误做法",
            "right_action": "审计合规做法",
            "impact_level": "中",
        },
    )
    assert r.status_code == 201, r.text
    pitfall_id = r.json()["pitfall_id"]

    audit = _latest_audit("pitfalls")
    assert audit is not None
    assert audit["action"] == "CREATE"
    assert audit["resource_id"] == pitfall_id

    conn = sqlite3.connect(TEST_DB)
    conn.execute("DELETE FROM stage_pitfall_ref WHERE pitfall_id=?", (pitfall_id,))
    conn.execute("DELETE FROM pitfall_guide WHERE pitfall_id=?", (pitfall_id,))
    conn.commit()
    conn.close()


def test_user_create_and_update_write_audit(admin_client):
    r = admin_client.post(
        "/api/auth/users",
        json={
            "username": "audit_user_tmp",
            "password": "audit-pass-1234",
            "role": "viewer",
            "display_name": "审计临时户",
        },
    )
    assert r.status_code == 201, r.text
    uid = r.json()["user_id"]

    create_audit = _latest_audit("users")
    assert create_audit is not None
    assert create_audit["action"] == "CREATE"
    assert create_audit["resource_id"] == uid
    assert create_audit["actor"] == "pytest_admin"

    r2 = admin_client.patch(
        f"/api/auth/users/{uid}",
        json={"role": "operator"},
    )
    assert r2.status_code == 200, r2.text

    update_audit = _latest_audit("users")
    assert update_audit is not None
    assert update_audit["action"] == "UPDATE"
    assert update_audit["resource_id"] == uid
    payload = json.loads(update_audit["payload"] or "{}")
    assert payload["before"]["role"] == "viewer"
    assert payload["after"]["role"] == "operator"

    conn = sqlite3.connect(TEST_DB)
    conn.execute("DELETE FROM users WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()


def test_patch_rejects_progress_percent_field(operator_client):
    """progress_percent 不在 ProjectUpdate schema，手改应被忽略或 422。"""
    projects = operator_client.get("/api/ops/projects").json()
    pid = projects[0]["project_id"]
    before = operator_client.get(f"/api/ops/projects/{pid}").json()["progress_percent"]

    r = operator_client.patch(
        f"/api/ops/projects/{pid}",
        json={"progress_percent": 99, "notes": "should-not-change-pct"},
    )
    # Pydantic 默认忽略额外字段 → 200，但百分比不变
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        after = operator_client.get(f"/api/ops/projects/{pid}").json()
        assert after["progress_percent"] == before
        assert after["notes"] == "should-not-change-pct"
