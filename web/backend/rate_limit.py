"""速率限制（slowapi）：防登录爆破、防批量建账号、防 DB 全量替换滥用。

key_func 选择：部署模式多样（本地 dev / nginx / Cloudflare Tunnel），
- 直接访问（request.client.host）= 真实 IP
- Cloudflare Tunnel: 真实 IP 在 CF-Connecting-IP
- nginx HTTPS 反代: 通常 X-Forwarded-For 第一个

优先级：CF-Connecting-IP > X-Forwarded-For[0] > 直连 IP。
环境变量 PMO_TRUST_PROXY_HEADER=true 时启用代理头解析；本地 dev 默认信任
X-Forwarded-For 便于 Vite proxy 调试（与 sh_eia 一致默认信任）。

端点级限制（写于各 router 装饰器）：
- POST /api/auth/login        10/minute（防爆破）
- POST /api/auth/users        10/hour  （防批量建号）
- POST /api/ops/import/db     5/hour   （替换库是毁灭性操作，限速）
"""
from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.status import HTTP_429_TOO_MANY_REQUESTS


def _trust_proxy() -> bool:
    return os.getenv("PMO_TRUST_PROXY_HEADER", "true").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def get_real_ip(request: Request) -> str:
    """提取真实客户端 IP。

    优先级：CF-Connecting-IP（Cloudflare）> X-Forwarded-For[0]（nginx）> 直连。
    PMO_TRUST_PROXY_HEADER=false 时不解析代理头，直接返回直连 IP。
    """
    if not _trust_proxy():
        return get_remote_address(request)
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return get_remote_address(request)


# default_limits 给未装饰的端点兜底：200/hour（同 qcc 基线）
limiter = Limiter(
    key_func=get_real_ip,
    default_limits=["200/hour"],
    headers_enabled=True,  # X-RateLimit-* 响应头，便于前端/客户端观察
)


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """自定义 429 响应：JSON 格式与本仓库现有错误体一致。"""
    return JSONResponse(
        status_code=HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": {
                "error": True,
                "code": "ERR_RATE_LIMITED",
                "message": f"请求过于频繁，请稍后再试。限制：{exc.detail}",
            }
        },
    )


def setup_rate_limit(app: FastAPI) -> Limiter:
    """注册 slowapi 中间件与异常处理器。"""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)
    return limiter