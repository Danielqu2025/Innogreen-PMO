"""Security headers middleware.

为所有响应附加防 XSS / clickjacking / MIME 嗅探 / 隐私泄露 的标准安全头。
HSTS 仅在 HTTPS 部署(经反代或 Cloudflare Tunnel)时下发;本地 HTTP 开发无副作用。

CSP 取保守值：default-src 'self';允许 'unsafe-inline' 给 antd 的运行时内联样式与脚本标签
（与 sh_eia 现状一致）。生产如需进一步加固，可改 nonce / hash。
"""
from __future__ import annotations

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


# 与 sh_eia 一致：frame-ancestors 'none' 防止点击劫持；form-action 'self' 限提交目标
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        response.headers.setdefault("Content-Security-Policy", _CSP)
        # HSTS: 仅在 HTTPS 场景下发。Cloudflare Tunnel / nginx HTTPS 反代后
        # request.url.scheme == "https" 或 X-Forwarded-Proto: https。
        if request.url.scheme == "https" or request.headers.get(
            "x-forwarded-proto"
        ) == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response