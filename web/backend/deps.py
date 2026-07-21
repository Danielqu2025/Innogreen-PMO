from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import Settings, get_settings

security = HTTPBearer(auto_error=False)


def require_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: Settings = Depends(get_settings),
) -> str:
    """Require Bearer token for /api/ops (read + write)."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": True, "code": "ERR_UNAUTHORIZED", "message": "缺少 Bearer Token"},
        )
    if credentials.credentials != settings.pmo_api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": True, "code": "ERR_UNAUTHORIZED", "message": "Token 无效"},
        )
    return credentials.credentials
