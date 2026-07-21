"""Shared pytest fixtures for PMO API tests (Phase C — session auth + 3 roles)."""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "test_api.db"
BACKEND = ROOT / "web" / "backend"
TEST_SESSION_SECRET = "test-session-secret-for-pytest-only-32chars"
TEST_ADMIN_USER = "pytest_admin"
TEST_ADMIN_PASS = "admin-pass-1234"
TEST_OPERATOR_USER = "pytest_operator"
TEST_OPERATOR_PASS = "operator-pass-1234"
TEST_VIEWER_USER = "pytest_viewer"
TEST_VIEWER_PASS = "viewer-pass-1234"

# DB path relative to web/ (config.py resolves relative to web/ directory)
os.environ["PMO_DB_PATH"] = str(Path("..").resolve().joinpath(TEST_DB))
os.environ["PMO_SESSION_SECRET"] = TEST_SESSION_SECRET
os.environ["PMO_BOOTSTRAP_ADMIN_USERNAME"] = ""
os.environ["PMO_BOOTSTRAP_ADMIN_PASSWORD"] = ""
os.environ["PMO_CORS_ORIGINS"] = "http://127.0.0.1:5173"

sys.path.insert(0, str(BACKEND))


def _init_test_db() -> None:
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "init_db.py"),
            "--db-path",
            str(TEST_DB),
        ],
        check=True,
        cwd=str(ROOT),
    )


_init_test_db()


@pytest.fixture(scope="session")
def app():
    from config import get_settings

    get_settings.cache_clear()
    from main import app as application

    return application


@pytest.fixture(scope="function")
def client(app):
    """Anonymous TestClient — no session (for 401/unauthenticated tests)."""
    with TestClient(app) as c:
        yield c


def _seed_test_users() -> None:
    from security import hash_password

    conn = sqlite3.connect(TEST_DB)
    for uname, pw, role in [
        (TEST_ADMIN_USER, TEST_ADMIN_PASS, "admin"),
        (TEST_OPERATOR_USER, TEST_OPERATOR_PASS, "operator"),
        (TEST_VIEWER_USER, TEST_VIEWER_PASS, "viewer"),
    ]:
        # DELETE + INSERT so bcrypt salt is fresh each run
        conn.execute("DELETE FROM users WHERE username=?", (uname,))
        conn.execute(
            "INSERT INTO users (username, password_hash, role, is_active) VALUES (?, ?, ?, 1)",
            (uname, hash_password(pw), role),
        )
    conn.commit()
    conn.close()


@pytest.fixture(scope="function")
def admin_client(app):
    """Admin TestClient — all write ops + user management."""
    _seed_test_users()
    with TestClient(app) as client:
        r = client.post(
            "/api/auth/login",
            json={"username": TEST_ADMIN_USER, "password": TEST_ADMIN_PASS},
        )
        assert r.status_code == 200, f"admin login failed: {r.text}"
        yield client


@pytest.fixture(scope="function")
def operator_client(app):
    """Operator TestClient — read + write (Phase C ops)."""
    _seed_test_users()
    with TestClient(app) as client:
        r = client.post(
            "/api/auth/login",
            json={"username": TEST_OPERATOR_USER, "password": TEST_OPERATOR_PASS},
        )
        assert r.status_code == 200, f"operator login failed: {r.text}"
        yield client


@pytest.fixture(scope="function")
def viewer_client(app):
    """Viewer TestClient — read-only, all writes → 403."""
    _seed_test_users()
    with TestClient(app) as client:
        r = client.post(
            "/api/auth/login",
            json={"username": TEST_VIEWER_USER, "password": TEST_VIEWER_PASS},
        )
        assert r.status_code == 200, f"viewer login failed: {r.text}"
        yield client


@pytest.fixture(scope="function")
def ent01(operator_client):
    """ENT-01 project + progress snapshot; restores tasks 18/19 after test."""
    projects = operator_client.get("/api/ops/projects").json()
    project = next(p for p in projects if p["project_code"] == "ENT-01")
    pid = project["project_id"]
    progress = operator_client.get(f"/api/ops/projects/{pid}/progress").json()
    by_task = {row["task_id"]: row for row in progress}
    original_task_ids = set(by_task.keys())

    snapshot = {
        18: {
            "status": by_task[18]["status"],
            "assigned_to": by_task[18]["assigned_to"],
            "blocker_note": by_task[18].get("blocker_note"),
        },
        19: {
            "status": by_task[19]["status"],
            "assigned_to": by_task[19]["assigned_to"],
            "blocker_note": by_task[19].get("blocker_note"),
        },
    }

    yield {"project_id": pid, "project": project}

    # Restore original state
    for task_id, body in snapshot.items():
        operator_client.put(
            f"/api/ops/projects/{pid}/tasks/{task_id}",
            json=body,
        )

    conn = sqlite3.connect(TEST_DB)
    for task_id in range(1, 108):
        if task_id not in original_task_ids:
            conn.execute(
                "DELETE FROM project_progress WHERE project_id=? AND task_id=?",
                (pid, task_id),
            )
    conn.commit()
    conn.close()
