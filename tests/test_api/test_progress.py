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
    # 卡点不再单独覆盖阶段；阶段按已触达最大阶段（此处仍为阶段 3 前期审批）
    assert project["current_stage_id"] == 3

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


def test_auto_stage_advances_on_later_stage_touch(operator_client: TestClient, ent01):
    """出现下一阶段工作记录（进行中）→ 自动进入该阶段。"""
    pid = ent01["project_id"]
    assert ent01["project"]["current_stage_id"] == 3

    response = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/72",  # stage 5 施工审批
        json={"status": "进行中", "assigned_to": "测试"},
    )
    assert response.status_code == 200

    project = operator_client.get(f"/api/ops/projects/{pid}").json()
    assert project["current_stage_id"] == 5


def test_auto_stage_ignores_utility_stage(operator_client: TestClient, ent01):
    """仅有公用工程阶段进度时，不把当前阶段写成该阶段，仍停在已触达主链最大阶段。"""
    pid = ent01["project_id"]

    response = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/33",  # stage 4 公用工程
        json={"status": "进行中", "assigned_to": "测试"},
    )
    assert response.status_code == 200

    project = operator_client.get(f"/api/ops/projects/{pid}").json()
    assert project["current_stage_id"] == 3


def test_auto_stage_ignores_pending_status(operator_client: TestClient):
    """待开始不计入触达；进行中才推进阶段。"""
    create = operator_client.post(
        "/api/ops/projects",
        json={
            "project_code": "ENT-PY-STAGE",
            "company_name": "ENT-PY-STAGE",
            "short_name": "PAS",
        },
    )
    assert create.status_code == 201
    pid = create.json()["project_id"]
    assert create.json()["current_stage_id"] is None

    pending = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/4",  # stage 1
        json={"status": "待开始", "assigned_to": "测试"},
    )
    assert pending.status_code == 200
    assert operator_client.get(f"/api/ops/projects/{pid}").json()["current_stage_id"] is None

    active = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/4",
        json={"status": "进行中", "assigned_to": "测试"},
    )
    assert active.status_code == 200
    assert operator_client.get(f"/api/ops/projects/{pid}").json()["current_stage_id"] == 1


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
