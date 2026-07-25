"""Portal SSO 客户端：验会话 / 代理登录。

开启条件：settings.pmo_portal_base_url 非空。
与 Portal 共用 SESSION_SECRET（PMO_SESSION_SECRET == Portal SESSION_SECRET）。
"""
from __future__ import annotations

import httpx
from fastapi import HTTPException, Request, Response, status

from config import get_settings

APP_CODE = "PMO"


def portal_enabled() -> bool:
    return bool(get_settings().pmo_portal_base_url.strip())


def _portal_base() -> str:
    return get_settings().pmo_portal_base_url.rstrip("/")


def _cookie_header(request: Request) -> str:
    return request.headers.get("cookie") or ""


def _forward_cookies(portal_response: httpx.Response, response: Response) -> None:
    settings = get_settings()
    domain = settings.pmo_session_cookie_domain or None
    for name, value in portal_response.cookies.items():
        response.set_cookie(
            key=name,
            value=value,
            path="/",
            domain=domain,
            httponly=True,
            samesite="lax",
            secure=settings.pmo_https_only,
            max_age=60 * 60 * 24 * 7,
        )


def verify_session(request: Request) -> dict | None:
    """调 Portal verify-session?app=PMO；无效返回 None。"""
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(
                f"{_portal_base()}/api/auth/verify-session",
                params={"app": APP_CODE},
                headers={"Cookie": _cookie_header(request)},
            )
    except httpx.HTTPError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": True,
                "code": "ERR_PORTAL_UNAVAILABLE",
                "message": "统一认证服务不可用，请稍后重试",
            },
        ) from None

    if r.status_code != 200:
        return None
    data = r.json()
    if not data.get("valid") or not data.get("user") or not data.get("role"):
        return None
    u = data["user"]
    return {
        "user_id": int(u["user_id"]),
        "username": u["username"],
        "display_name": u.get("display_name"),
        "role": data["role"],
        "is_active": bool(u.get("is_active", True)),
        "created_at": u.get("created_at"),
    }


def proxy_login(username: str, password: str, response: Response) -> dict:
    """把登录转到 Portal，Set-Cookie 回写浏览器；返回 PMO 角色用户信息。"""
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(
                f"{_portal_base()}/api/auth/login",
                json={"username": username, "password": password},
            )
    except httpx.HTTPError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": True,
                "code": "ERR_PORTAL_UNAVAILABLE",
                "message": "统一认证服务不可用，请稍后重试",
            },
        ) from None

    if r.status_code != 200:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"error": True, "code": "ERR_UNAUTHORIZED", "message": "用户名或密码错误"},
        )

    _forward_cookies(r, response)
    cookie_header = "; ".join(f"{name}={value}" for name, value in r.cookies.items())

    try:
        with httpx.Client(timeout=5.0) as client:
            vr = client.get(
                f"{_portal_base()}/api/auth/verify-session",
                params={"app": APP_CODE},
                headers={"Cookie": cookie_header},
            )
    except httpx.HTTPError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": True,
                "code": "ERR_PORTAL_UNAVAILABLE",
                "message": "统一认证服务不可用，请稍后重试",
            },
        ) from None

    if vr.status_code != 200 or not vr.json().get("valid"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "error": True,
                "code": "ERR_NO_APP_ACCESS",
                "message": "账号未授权访问 PMO，请联系管理员",
            },
        )

    u = r.json()
    v = vr.json()
    return {
        "user_id": int(u["user_id"]),
        "username": u["username"],
        "display_name": u.get("display_name"),
        "role": v["role"],
        "is_active": True,
        "created_at": u.get("created_at"),
    }


def proxy_logout(request: Request, response: Response) -> None:
    """通知 Portal 清会话，并清除本地 cookie。"""
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(
                f"{_portal_base()}/api/auth/logout",
                headers={"Cookie": _cookie_header(request)},
            )
    except httpx.HTTPError:
        pass
    response.delete_cookie(
        get_settings().pmo_session_cookie_name,
        path="/",
        domain=get_settings().pmo_session_cookie_domain or None,
    )
    response.delete_cookie("session", path="/")  # 兼容旧名
