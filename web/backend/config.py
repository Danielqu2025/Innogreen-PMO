from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    pmo_db_path: str = str(ROOT / "data" / "innogreen_pmo.db")
    # 会话签名密钥（必填：未设则 Settings 校验失败、应用拒绝启动——刻意的安全闸）
    pmo_session_secret: str
    # 首个管理员引导种子（仅 users 表为空时生效，用于冷启动建一号管理员）
    pmo_bootstrap_admin_username: str | None = None
    pmo_bootstrap_admin_password: str | None = None
    pmo_host: str = "127.0.0.1"
    pmo_port: int = 8000
    pmo_enable_docs: bool = True
    pmo_cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    # 会话 cookie 是否仅 HTTPS（生产 HTTPS 反代后设 true）
    pmo_https_only: bool = False

    @field_validator("pmo_cors_origins")
    @classmethod
    def _no_wildcard_cors(cls, v: str) -> str:
        # allow_credentials=True 下不能用通配源，否则浏览器静默拒绝凭据 → 前端登录全挂
        if any(o.strip() == "*" for o in v.split(",")):
            raise ValueError("PMO_CORS_ORIGINS 不能包含 '*'（与 allow_credentials=True 冲突）")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.pmo_cors_origins.split(",") if o.strip()]

    @property
    def db_path(self) -> Path:
        path = Path(self.pmo_db_path)
        if not path.is_absolute():
            path = (Path(__file__).resolve().parents[1] / path).resolve()
        return path

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path.as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
