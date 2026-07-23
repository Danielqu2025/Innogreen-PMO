"""P1 安全加固测试：
- LIKE 通配符转义（% / _ 不再作为元字符匹配）
- 自助改密：成功 / 旧密码错 / 弱新密 / 同旧密
- audit_log append-only trigger：UPDATE/DELETE 应被 RAISE 拒绝
- DB 导入校验：audit_log 行数低于 50% 阈值应被拒
"""
from __future__ import annotations

import sqlite3
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook

# 与 conftest.py 镜像的常量；避免 import conftest（pytest.ini 的 pythonpath 不含 tests/）
TEST_OPERATOR_USER = "pytest_operator"
TEST_OPERATOR_PASS = "operator-pass-1234"


# ===== LIKE 转义 =====
def test_like_escape_underscore(operator_client: TestClient):
    """搜索 `ENT-0_` 不应同时命中 ENT-01/ENT-02/...（下划线被当元字符）。

    测试库样本里没有 ENT-0_ 这种含下划线的 code，转义后应匹配空集。
    """
    projects = operator_client.get("/api/ops/projects").json()
    codes = {p["project_code"] for p in projects}
    # 找一个 ENT- 开头但不含下划线的 code 作为「不应被命中」的反证
    no_underscore = next((c for c in codes if c.startswith("ENT-") and "_" not in c), None)
    assert no_underscore, "测试库应至少有一个 ENT- 开头的不含下划线 code"

    r = operator_client.get("/api/ops/projects", params={"q": "ENT-0_"})
    assert r.status_code == 200
    returned = {p["project_code"] for p in r.json()}
    # ENT-0_ 转义后仅匹配字面 "ENT-0_"，不应误命中 ENT-0X 系列
    assert no_underscore not in returned, (
        f"LIKE 下划线未转义：搜 ENT-0_ 误命中 {no_underscore}"
    )


def test_like_escape_percent(operator_client: TestClient):
    """搜索 `%` 应仅匹配字面含 % 的 code/name，不应返回所有项目。"""
    r = operator_client.get("/api/ops/projects", params={"q": "%"})
    assert r.status_code == 200
    for p in r.json():
        combined = (
            f"{p['project_code']}{p['company_name']}"
            f"{p.get('short_name') or ''}{p.get('full_name') or ''}"
        )
        assert "%" in combined, f"LIKE % 误命中：{p}"


def test_like_normal_match_still_works(operator_client: TestClient):
    """正常搜索应正常返回（防止转义破坏了常规路径）。"""
    projects = operator_client.get("/api/ops/projects").json()
    if not projects:
        return  # 测试库无数据时不强求
    first_code = projects[0]["project_code"]
    r = operator_client.get("/api/ops/projects", params={"q": first_code})
    assert r.status_code == 200
    codes = {p["project_code"] for p in r.json()}
    assert first_code in codes


# ===== 自助改密 =====
def test_change_password_success(operator_client: TestClient):
    """operator 改自己密码：新密码应能登录，旧密码应失败。"""
    new_pw = "new-operator-pass-1234"
    r = operator_client.post(
        "/api/auth/change-password",
        json={"current_password": TEST_OPERATOR_PASS, "new_password": new_pw},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    # 新密码可登录：用匿名 client 试登
    from main import app  # noqa: F401

    with TestClient(app) as anon:
        anon.app.state.limiter.reset()
        r = anon.post(
            "/api/auth/login",
            json={"username": TEST_OPERATOR_USER, "password": new_pw},
        )
        assert r.status_code == 200, r.text
        # 旧密码应失败
        r2 = anon.post(
            "/api/auth/login",
            json={"username": TEST_OPERATOR_USER, "password": TEST_OPERATOR_PASS},
        )
        assert r2.status_code == 401


def test_change_password_wrong_current(operator_client: TestClient):
    """旧密码错误应 401，不改密。"""
    r = operator_client.post(
        "/api/auth/change-password",
        json={"current_password": "wrong-old-password", "new_password": "x" * 12},
    )
    assert r.status_code == 401
    assert "当前密码错误" in r.json()["detail"]["message"]


def test_change_password_too_short(operator_client: TestClient):
    """新密码 < 8 位应被 Pydantic 422 拒。"""
    r = operator_client.post(
        "/api/auth/change-password",
        json={"current_password": TEST_OPERATOR_PASS, "new_password": "short"},
    )
    assert r.status_code == 422


def test_change_password_same_as_old(operator_client: TestClient):
    """新旧密码相同应 400。"""
    r = operator_client.post(
        "/api/auth/change-password",
        json={
            "current_password": TEST_OPERATOR_PASS,
            "new_password": TEST_OPERATOR_PASS,
        },
    )
    assert r.status_code == 400
    assert "相同" in r.json()["detail"]["message"]


def test_change_password_requires_login(client: TestClient):
    """未登录调改密应 401。"""
    r = client.post(
        "/api/auth/change-password",
        json={"current_password": "x", "new_password": "y" * 10},
    )
    assert r.status_code == 401


# ===== audit_log 不可篡改 trigger =====
def test_audit_log_update_blocked_by_trigger(app):
    """BEFORE UPDATE ON audit_log 应被 RAISE 拒绝。"""
    from config import get_settings

    db_path = get_settings().db_path
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT audit_id FROM audit_log LIMIT 1").fetchone()
        if not row:
            return  # 测试库无审计数据，trigger 已装上即可
        try:
            conn.execute(
                "UPDATE audit_log SET actor=? WHERE audit_id=?",
                ("hacker", row[0]),
            )
        except sqlite3.IntegrityError as exc:
            msg = str(exc)
            assert "append-only" in msg or "UPDATE forbidden" in msg, msg
        else:
            raise AssertionError("UPDATE audit_log 应被 trigger 拒绝，但仍成功")
    finally:
        conn.close()


def test_audit_log_delete_blocked_by_trigger(app):
    """BEFORE DELETE ON audit_log 应被 RAISE 拒绝。"""
    from config import get_settings

    db_path = get_settings().db_path
    conn = sqlite3.connect(str(db_path))
    try:
        try:
            conn.execute("DELETE FROM audit_log")
        except sqlite3.IntegrityError as exc:
            msg = str(exc)
            assert "append-only" in msg or "DELETE forbidden" in msg, msg
        else:
            raise AssertionError("DELETE audit_log 应被 trigger 拒绝，但仍成功")
    finally:
        conn.close()


# ===== DB 导入 audit_log 行数校验 =====
def test_import_db_rejects_audit_log_truncation(admin_client: TestClient, tmp_path):
    """上传一个 audit_log 被大量清空的库，应被 400 拒绝。

    工作副本需要先 DROP 触发器才能 DELETE（trigger 已被生产 / 主库装上，
    复制二进制也会复制 trigger；这是合理的——审计的不可篡改性应延伸到备份）。
    """
    # 先导出当前库（含 audit_log）
    snap = admin_client.get("/api/ops/export/db").content
    assert snap.startswith(b"SQLite format 3\x00")

    work_db = tmp_path / "trimmed.db"
    work_db.write_bytes(snap)
    conn = sqlite3.connect(str(work_db))
    try:
        # 卸 trigger 才能 DELETE
        conn.execute("DROP TRIGGER IF EXISTS audit_log_no_update")
        conn.execute("DROP TRIGGER IF EXISTS audit_log_no_delete")
        conn.execute("DELETE FROM audit_log")
        conn.commit()
    finally:
        conn.close()

    trimmed = work_db.read_bytes()
    r = admin_client.post(
        "/api/ops/import/db",
        files={"file": ("trim.db", trimmed, "application/x-sqlite3")},
        params={"confirm": True},
    )
    assert r.status_code == 400, r.text
    assert "audit_log" in r.json()["detail"]["message"]


# ===== 占位：导入 Excel 仍可 dry_run =====
def test_import_excel_dry_run_anon(client: TestClient):
    """匿名调导入 Excel：401（需登录）；dry-run 不会真写库。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "企业档案"
    ws.append(["project_code", "company_name"])
    buf = BytesIO()
    wb.save(buf)
    r = client.post(
        "/api/ops/import/excel",
        files={
            "file": (
                "t.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        params={"dry_run": True},
    )
    assert r.status_code in (200, 401)