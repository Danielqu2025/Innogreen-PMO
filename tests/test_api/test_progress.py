"""Phase C progress tests — operator_client (session cookie)."""
from fastapi.testclient import TestClient


def test_progress_complete_sets_completed_at(operator_client: TestClient, ent01):
    pid = ent01["project_id"]
    response = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/18",
        json={"status": "已完成", "assigned_to": "李四"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "已完成"
    assert body["completed_at"] is not None

    project = operator_client.get(f"/api/ops/projects/{pid}").json()
    assert project["progress_percent"] >= ent01["project"]["progress_percent"]


def test_blocker_syncs_project_status(operator_client: TestClient, ent01):
    pid = ent01["project_id"]

    # 先 resolve 任务 19（如果它还是卡点的话）
    operator_client.put(
        f"/api/ops/projects/{pid}/tasks/19",
        json={"status": "已完成", "assigned_to": "李四"},
    )

    response = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/20",
        json={
            "status": "卡点",
            "assigned_to": "王五",
            "blocker_note": "pytest 卡点测试",
        },
    )
    assert response.status_code == 200

    project = operator_client.get(f"/api/ops/projects/{pid}").json()
    assert project["project_status"] == "卡点"

    blockers = operator_client.get("/api/ops/progress/blockers").json()
    assert any(b["project_id"] == pid and b["task_id"] == 20 for b in blockers)


def test_resolve_blocker_restores_in_progress(operator_client: TestClient, ent01):
    pid = ent01["project_id"]
    operator_client.put(
        f"/api/ops/projects/{pid}/tasks/19",
        json={"status": "已完成", "assigned_to": "李四"},
    )
    operator_client.put(
        f"/api/ops/projects/{pid}/tasks/20",
        json={"status": "已完成", "assigned_to": "王五"},
    )

    project = operator_client.get(f"/api/ops/projects/{pid}").json()
    assert project["project_status"] == "进行中"


def test_progress_invalid_status(operator_client: TestClient, ent01):
    pid = ent01["project_id"]
    response = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/18",
        json={"status": "无效状态"},
    )
    assert response.status_code == 400


def test_critical_path_for_project(operator_client: TestClient, ent01):
    pid = ent01["project_id"]
    response = operator_client.get(f"/api/ops/projects/{pid}/critical-path")
    assert response.status_code == 200
    body = response.json()
    assert body["project_code"] == "ENT-01"
    assert len(body["nodes"]) > 0
