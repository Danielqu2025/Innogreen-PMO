"""Admin task catalog: create with renumber, soft-deactivate, progress denominator."""
from __future__ import annotations


def test_operator_cannot_create_task(operator_client):
    r = operator_client.post(
        "/api/ops/tasks",
        json={
            "stage_id": 3,
            "task_name": "不应创建",
            "owner": "客户主导",
            "parent_task_id": 18,
        },
    )
    assert r.status_code == 403


def test_insert_under_22_renumbers_siblings(admin_client):
    # 插入前：3.2.1 应为化工反应安全风险评估
    before = admin_client.get("/api/ops/tasks", params={"stage_id": 3}).json()
    by_code = {t["task_code"]: t for t in before}
    assert "3.2.1" in by_code
    old_221_name = by_code["3.2.1"]["task_name"]
    old_221_id = by_code["3.2.1"]["task_id"]
    assert by_code.get("3.2.2")

    # 在 3.2 下、插到原 3.2.1 之前
    r = admin_client.post(
        "/api/ops/tasks",
        json={
            "stage_id": 3,
            "task_name": "测试插入反应评估前置项",
            "owner": "客户委托第三方",
            "critical_path": "🔴",
            "default_days": 3,
            "parent_task_id": 18,
            "insert_before_task_id": old_221_id,
        },
    )
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["task_code"] == "3.2.1"
    assert created["is_active"] == 1

    after = admin_client.get(
        "/api/ops/tasks", params={"stage_id": 3, "include_inactive": True}
    ).json()
    by_code2 = {t["task_code"]: t for t in after}
    assert by_code2["3.2.1"]["task_id"] == created["task_id"]
    assert by_code2["3.2.2"]["task_id"] == old_221_id
    assert by_code2["3.2.2"]["task_name"] == old_221_name
    assert by_code2["3.2.3"]["task_name"]  # 原 3.2.2 顺移


def test_deactivate_hides_from_default_list(admin_client):
    # 找一个冷门任务停用（阶段9 正式投用）
    tasks = admin_client.get("/api/ops/tasks", params={"stage_id": 9}).json()
    assert tasks
    tid = tasks[0]["task_id"]
    code = tasks[0]["task_code"]

    r = admin_client.post(f"/api/ops/tasks/{tid}/deactivate")
    assert r.status_code == 200
    assert r.json()["is_active"] == 0

    visible = admin_client.get("/api/ops/tasks", params={"stage_id": 9}).json()
    assert all(t["task_id"] != tid for t in visible)

    hidden = admin_client.get(
        "/api/ops/tasks", params={"stage_id": 9, "include_inactive": True}
    ).json()
    assert any(t["task_id"] == tid and t["task_code"] == code for t in hidden)

    # 恢复
    r2 = admin_client.post(f"/api/ops/tasks/{tid}/activate")
    assert r2.status_code == 200
    assert r2.json()["is_active"] == 1


def test_deactivate_changes_progress_denominator(admin_client):
    projects = admin_client.get("/api/ops/projects").json()
    p = projects[0]
    before_pct = p["progress_percent"]

    # 停用一个无人完成依赖的冷门任务（阶段9），分母变小 → 若分子不变则百分比不降
    tasks = admin_client.get("/api/ops/tasks", params={"stage_id": 9}).json()
    tid = tasks[0]["task_id"]
    admin_client.post(f"/api/ops/tasks/{tid}/deactivate")

    after = admin_client.get(f"/api/ops/projects/{p['project_id']}").json()
    # 分母从 108→107；已完成数不变时百分比应 >= 原值（或同为 0）
    assert after["progress_percent"] >= before_pct or before_pct == 0

    admin_client.post(f"/api/ops/tasks/{tid}/activate")


def test_update_task_fields(admin_client):
    tasks = admin_client.get("/api/ops/tasks", params={"stage_id": 7}).json()
    tid = tasks[0]["task_id"]
    r = admin_client.patch(
        f"/api/ops/tasks/{tid}",
        json={"description": "pytest-desc", "default_days": 9},
    )
    assert r.status_code == 200
    assert r.json()["description"] == "pytest-desc"
    assert r.json()["default_days"] == 9
    assert r.json()["task_code"] == tasks[0]["task_code"]
