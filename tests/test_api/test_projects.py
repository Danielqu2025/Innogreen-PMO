"""Phase C projects tests — operator_client (session cookie)."""
from fastapi.testclient import TestClient


def test_list_projects_returns_sample_data(operator_client: TestClient):
    response = operator_client.get("/api/ops/projects")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) >= 3
    codes = {r["project_code"] for r in rows}
    assert "ENT-01" in codes


def test_filter_by_status_blocker(operator_client: TestClient):
    response = operator_client.get(
        "/api/ops/projects",
        params={"status": "卡点"},
    )
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) >= 1
    assert all(r["project_status"] == "卡点" for r in rows)


def test_create_and_patch_project(operator_client: TestClient):
    create = operator_client.post(
        "/api/ops/projects",
        json={
            "project_code": "ENT-PYTEST",
            "company_name": "ENT-PYTEST",
            "business_type": "研发",
            "building": "T-1",
        },
    )
    assert create.status_code == 201
    created = create.json()
    pid = created["project_id"]
    assert created["project_status"] == "未开始"
    assert created["progress_percent"] == 0

    duplicate = operator_client.post(
        "/api/ops/projects",
        json={"project_code": "ENT-PYTEST", "company_name": "ENT-PYTEST"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "ERR_CONFLICT"

    patch = operator_client.patch(
        f"/api/ops/projects/{pid}",
        json={"project_status": "进行中", "notes": "pytest"},
    )
    assert patch.status_code == 200
    assert patch.json()["project_status"] == "进行中"
    assert patch.json()["notes"] == "pytest"

    missing = operator_client.patch(
        "/api/ops/projects/99999",
        json={"notes": "nope"},
    )
    assert missing.status_code == 404


def test_get_project_not_found(operator_client: TestClient):
    response = operator_client.get("/api/ops/projects/99999")
    assert response.status_code == 404


# ── admin: user management guards ──────────────────────────────────────────────

def test_admin_create_user(admin_client: TestClient):
    r = admin_client.post(
        "/api/auth/users",
        json={"username": "new_op", "password": "newpass123", "role": "operator"},
    )
    assert r.status_code == 201
    assert r.json()["role"] == "operator"


def test_admin_last_admin_guard(admin_client: TestClient):
    """Cannot demote last active admin."""
    users = admin_client.get("/api/auth/users").json()
    my_id = next(u["user_id"] for u in users if u["role"] == "admin")
    r = admin_client.patch(f"/api/auth/users/{my_id}", json={"role": "operator"})
    assert r.status_code == 409
    assert "管理员" in r.json()["detail"]["message"]


def test_admin_self_disable_guard(admin_client: TestClient):
    """Cannot disable own account."""
    users = admin_client.get("/api/auth/users").json()
    my_id = next(u["user_id"] for u in users if u["role"] == "admin")
    r = admin_client.patch(f"/api/auth/users/{my_id}", json={"is_active": False})
    assert r.status_code == 409
    assert "禁用" in r.json()["detail"]["message"] or "自己的" in r.json()["detail"]["message"]
