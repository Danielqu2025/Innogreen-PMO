"""Phase C 鉴权测试：登录/登出/会话/me + 角色门禁 + viewer 写矩阵（关键安全网）."""
from fastapi.testclient import TestClient

# Test user credentials (mirrored from conftest — no extra import path needed here)
VIEWER_USER = "pytest_viewer"
VIEWER_PASS = "viewer-pass-1234"


def test_write_without_session_returns_401(client: TestClient):
    """未登录写任何受保护端点均 401。"""
    for method, url, body in [
        ("post", "/api/ops/projects", {"project_code": "X", "company_name": "X"}),
        ("patch", "/api/ops/projects/1", {"notes": "x"}),
        ("put", "/api/ops/projects/1/tasks/1", {"status": "进行中"}),
        ("post", "/api/ops/pitfalls", {"stage_ref": "立项", "wrong_action": "x", "right_action": "y"}),
    ]:
        r = getattr(client, method)(url, json=body)
        assert r.status_code == 401, f"{method.upper()} {url} → {r.status_code} (want 401)"


def test_login_success(admin_client: TestClient):
    r = admin_client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_login_wrong_password_returns_401(client: TestClient):
    r = client.post("/api/auth/login", json={"username": "pytest_admin", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["detail"]["message"] == "用户名或密码错误"


def test_login_nonexistent_returns_401(client: TestClient):
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
    assert r.status_code == 401
    assert r.json()["detail"]["message"] == "用户名或密码错误"


def test_login_inactive_user_returns_401(admin_client: TestClient, app):
    """Disabled user login → 401 (same generic message as wrong password)."""
    users = admin_client.get("/api/auth/users").json()
    vid = next(u["user_id"] for u in users if u["role"] == "viewer")
    admin_client.patch(f"/api/auth/users/{vid}", json={"is_active": False})

    # Use a fresh client so there is no pre-existing session
    with TestClient(app) as anon:
        r = anon.post(
            "/api/auth/login",
            json={"username": VIEWER_USER, "password": VIEWER_PASS},
        )
        assert r.status_code == 401
        assert r.json()["detail"]["message"] == "用户名或密码错误"


def test_logout_clears_session(admin_client: TestClient):
    r = admin_client.post("/api/auth/logout")
    assert r.status_code == 200
    r2 = admin_client.get("/api/auth/me")
    assert r2.status_code == 401


def test_me_returns_current_user(admin_client: TestClient):
    r = admin_client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["username"] == "pytest_admin"


# ── viewer 写矩阵：关键安全网（防止"忘加 WriteUser"回归） ──────────────────

def test_viewer_cannot_create_project(viewer_client: TestClient):
    r = viewer_client.post("/api/ops/projects", json={"project_code": "X", "company_name": "X"})
    assert r.status_code == 403


def test_viewer_cannot_patch_project(viewer_client: TestClient):
    r = viewer_client.patch("/api/ops/projects/1", json={"notes": "x"})
    assert r.status_code == 403


def test_viewer_cannot_update_progress(viewer_client: TestClient):
    r = viewer_client.put("/api/ops/projects/1/tasks/1", json={"status": "进行中"})
    assert r.status_code == 403


def test_viewer_cannot_create_pitfall(viewer_client: TestClient):
    r = viewer_client.post(
        "/api/ops/pitfalls",
        json={"stage_ref": "立项", "wrong_action": "x", "right_action": "y"},
    )
    assert r.status_code == 403


def test_viewer_cannot_list_users(viewer_client: TestClient):
    r = viewer_client.get("/api/auth/users")
    assert r.status_code == 403


def test_viewer_cannot_create_user(viewer_client: TestClient):
    r = viewer_client.post(
        "/api/auth/users",
        json={"username": "hacker", "password": "pw12345678", "role": "admin"},
    )
    assert r.status_code == 403


def test_viewer_cannot_update_user(viewer_client: TestClient):
    r = viewer_client.patch("/api/auth/users/1", json={"is_active": False})
    assert r.status_code == 403


def test_viewer_can_read_dashboard(viewer_client: TestClient):
    r = viewer_client.get("/api/ops/dashboard/summary")
    assert r.status_code == 200


def test_viewer_can_read_projects(viewer_client: TestClient):
    r = viewer_client.get("/api/ops/projects")
    assert r.status_code == 200
