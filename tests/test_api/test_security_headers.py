"""P0 安全加固测试：
- SecurityHeadersMiddleware 必备响应头
- slowapi 速率限制触发（登录 10/minute、建用户 10/hour、DB 替换 5/hour）
- pmo_enable_docs 默认 false
- pmo_session_secret 弱值校验

依赖：依赖 limiter.reset() 的 conftest 已把跨测试配额清零，
这里用更小的窗口（< 默认配额）保证不误伤其他用例。
"""
from fastapi.testclient import TestClient


def test_security_headers_present(client: TestClient):
    """所有响应必须含防 XSS / clickjacking / MIME 嗅探的头。"""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "camera=()" in r.headers.get("Permissions-Policy", "")
    assert "frame-ancestors 'none'" in r.headers.get("Content-Security-Policy", "")
    # HSTS 仅在 https / x-forwarded-proto=https 时下发；测试 client 是 http 故不应有
    assert "Strict-Transport-Security" not in r.headers


def test_security_headers_hsts_on_https(app):
    """模拟经 HTTPS 反代：x-forwarded-proto=https 应触发 HSTS。"""
    with TestClient(app) as c:
        r = c.get("/health", headers={"x-forwarded-proto": "https"})
        assert r.status_code == 200
        assert "max-age=" in r.headers.get("Strict-Transport-Security", "")


def test_login_rate_limit(app):
    """登录 10/minute：第 11 次同 IP 应触发 429。"""
    with TestClient(app) as anon:
        # 重置保证本次独立
        anon.app.state.limiter.reset()
        for _ in range(10):
            r = anon.post(
                "/api/auth/login",
                json={"username": "nobody", "password": "wrong"},
            )
            # 错密码统一 401，未触发限流
            assert r.status_code == 401, r.text
        # 第 11 次：限流 → 429
        r = anon.post(
            "/api/auth/login",
            json={"username": "nobody", "password": "wrong"},
        )
        assert r.status_code == 429, r.text
        body = r.json()
        assert body["detail"]["code"] == "ERR_RATE_LIMITED"


def test_create_user_rate_limit(admin_client: TestClient):
    """建用户 10/hour：每个测试 limiter 已 reset，第 11 次 429。"""
    admin_client.app.state.limiter.reset()
    # 9 个失败尝试（用户名冲突不消耗额外的 201，但 limiter 仍计数）
    for i in range(9):
        r = admin_client.post(
            "/api/auth/users",
            json={
                "username": f"rl-test-{i}",
                "password": "password-12345",
                "role": "viewer",
            },
        )
        assert r.status_code == 201, r.text
    # 第 10 次：成功（10/hour 配额第 10 个）
    r = admin_client.post(
        "/api/auth/users",
        json={
            "username": "rl-test-9",
            "password": "password-12345",
            "role": "viewer",
        },
    )
    assert r.status_code == 201, r.text
    # 第 11 次：429
    r = admin_client.post(
        "/api/auth/users",
        json={
            "username": "rl-test-10",
            "password": "password-12345",
            "role": "viewer",
        },
    )
    assert r.status_code == 429, r.text


def test_import_db_rate_limit(admin_client: TestClient):
    """DB 替换 5/hour：第 6 次 429（无需真替换数据库，confirm=false 已先被拦在 400）。

    注意：限流在 confirm 校验之前。
    """
    admin_client.app.state.limiter.reset()
    for _ in range(5):
        r = admin_client.post(
            "/api/ops/import/db",
            files={"file": ("x.db", b"x", "application/x-sqlite3")},
            params={"confirm": False},
        )
        # confirm=False → 400，限流照样计 1 次
        assert r.status_code == 400, r.text
    r = admin_client.post(
        "/api/ops/import/db",
        files={"file": ("x.db", b"x", "application/x-sqlite3")},
        params={"confirm": False},
    )
    assert r.status_code == 429, r.text


def test_docs_disabled_by_default(client: TestClient):
    """pmo_enable_docs 默认 false → /docs、/redoc 应返回 404。"""
    r = client.get("/docs")
    assert r.status_code == 404
    r = client.get("/redoc")
    assert r.status_code == 404
    r = client.get("/openapi.json")
    # OpenAPI schema 仍可取（FastAPI 默认开 openapi_url）；只是文档 UI 不可访问。
    assert r.status_code == 200


def test_session_secret_length_validator():
    """弱 / 占位 secret 应在 Settings 校验阶段被拒。"""
    import importlib
    import sys

    sys.path.insert(0, "web/backend")
    # 移除可能已缓存的 config 模块，确保 env var 干净
    sys.modules.pop("config", None)

    base_env = {
        "PMO_DB_PATH": "/tmp/nonexistent_pmo.db",
        "PMO_CORS_ORIGINS": "http://127.0.0.1:5173",
        "PMO_BOOTSTRAP_ADMIN_USERNAME": "",
        "PMO_BOOTSTRAP_ADMIN_PASSWORD": "",
    }

    # 弱 secret：太短
    import os
    saved = {k: os.environ.get(k) for k in list(os.environ.keys()) if k.startswith("PMO_")}
    try:
        for k, v in base_env.items():
            os.environ[k] = v
        os.environ["PMO_SESSION_SECRET"] = "short"
        from config import Settings

        try:
            Settings()
        except Exception as e:
            assert "长度不足" in str(e), f"应拒绝弱 secret，但报：{e!r}"
        else:
            raise AssertionError("弱 secret 应被拒，但 Settings 接受了")

        # 占位 secret
        os.environ["PMO_SESSION_SECRET"] = "replace-with-output-of-secrets-token-hex-32"
        try:
            Settings()
        except Exception as e:
            assert "占位符" in str(e), f"应拒绝占位 secret，但报：{e!r}"
        else:
            raise AssertionError("占位 secret 应被拒，但 Settings 接受了")
    finally:
        # 恢复 conftest 设的 env，不污染后续测试
        for k in list(os.environ.keys()):
            if k.startswith("PMO_"):
                os.environ.pop(k, None)
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
        sys.modules.pop("config", None)