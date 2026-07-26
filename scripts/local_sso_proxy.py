"""本机同域路径反代（替代 nginx.innogreen-sso.conf，方便 Windows 试用）。

  http://127.0.0.1:8788/        → Portal :8001
  http://127.0.0.1:8788/pmo/    → PMO    :8800
  http://127.0.0.1:8788/qcc/    → qcc    :8765
  http://127.0.0.1:8788/eia/    → sh_eia :8080

用法：
  python scripts/local_sso_proxy.py
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.routing import Route

PORTAL = "http://127.0.0.1:8001"
PMO = "http://127.0.0.1:8800"
QCC = "http://127.0.0.1:8765"
EIA = "http://127.0.0.1:8080"
LISTEN = ("127.0.0.1", 8788)

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-encoding",
    "content-length",
}


async def _forward(request: Request, upstream: str, path: str) -> Response:
    url = f"{upstream}{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP and k.lower() != "host"
    }
    headers["host"] = upstream.split("://", 1)[1]
    headers["x-forwarded-proto"] = request.url.scheme
    headers["x-forwarded-host"] = request.headers.get("host", "127.0.0.1:8788")
    if upstream == PMO:
        headers["x-forwarded-prefix"] = "/pmo"
    elif upstream == QCC:
        headers["x-forwarded-prefix"] = "/qcc"
    elif upstream == EIA:
        headers["x-forwarded-prefix"] = "/eia"

    body = await request.body()
    client: httpx.AsyncClient = request.app.state.client
    req = client.build_request(
        request.method,
        url,
        headers=headers,
        content=body if body else None,
    )
    upstream_resp = await client.send(req, stream=True)

    out_headers = [
        (k, v)
        for k, v in upstream_resp.headers.multi_items()
        if k.lower() not in HOP_BY_HOP
    ]

    async def stream():
        try:
            async for chunk in upstream_resp.aiter_raw():
                yield chunk
        finally:
            await upstream_resp.aclose()

    return StreamingResponse(
        stream(),
        status_code=upstream_resp.status_code,
        headers=dict(out_headers),
    )


async def dispatch(request: Request) -> Response:
    path = request.url.path or "/"
    if path == "/pmo":
        return Response(status_code=307, headers={"location": "/pmo/"})
    if path == "/qcc":
        return Response(status_code=307, headers={"location": "/qcc/"})
    if path == "/eia":
        return Response(status_code=307, headers={"location": "/eia/"})

    if path.startswith("/pmo/"):
        return await _forward(request, PMO, path[4:] or "/")
    if path.startswith("/qcc/"):
        return await _forward(request, QCC, path[4:] or "/")
    if path.startswith("/eia/"):
        return await _forward(request, EIA, path[4:] or "/")
    return await _forward(request, PORTAL, path)


@asynccontextmanager
async def lifespan(app: Starlette):
    app.state.client = httpx.AsyncClient(timeout=None, follow_redirects=False)
    try:
        yield
    finally:
        await app.state.client.aclose()


app = Starlette(
    routes=[
        Route("/", dispatch, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]),
        Route(
            "/{path:path}",
            dispatch,
            methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        ),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    host, port = LISTEN
    print(f"[local-sso-proxy] http://{host}:{port}/  → portal/pmo/qcc/eia")
    uvicorn.run(app, host=host, port=port, log_level="info")
