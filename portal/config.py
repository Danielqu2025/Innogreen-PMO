from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]
_MIN_SECRET_LEN = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 会话密钥（必填；与 PMO 共用同一密钥，实现跨应用 cookie 互信）
    session_secret: str

    portal_db_path: str = str(ROOT / "data" / "portal.db")

    # 信任的应用列表（逗号分隔，用于 CORS 白名单）
    trusted_apps: str = "PMO,qcc,sh_eia"

    # CORS 允许的前端地址
    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:8765"

    # 会话 cookie（与 PMO/qcc 共用同名，同域路径 SSO）
    session_cookie_name: str = "innogreen_session"
    # 可选：跨子域共享时设 .example.com；同域路径路由留空
    session_cookie_domain: str = ""
    # 生产 HTTPS 反代后设 true
    https_only: bool = False

    # 冷启动管理员（Portal 自身 admin；首次启动写入 users + PMO/qcc membership）
    portal_bootstrap_admin_username: str | None = None
    portal_bootstrap_admin_password: str | None = None

    # Portal 服务地址（供其他应用回调 / 种子应用 URL 的公网基址）
    portal_base_url: str = "http://localhost:8001"
    # 同域路径部署时应用入口（覆盖 seed；留空则用 localhost 开发默认）
    pmo_public_url: str = ""
    qcc_public_url: str = ""
    sh_eia_public_url: str = ""

    # 合并迁移源库（可选；脚本也可通过 CLI 覆盖）
    pmo_users_db_path: str = ""
    qcc_users_db_path: str = ""
    sh_eia_users_db_path: str = ""

    @field_validator("session_secret")
    @classmethod
    def _strong_secret(cls, v: str) -> str:
        if len(v) < _MIN_SECRET_LEN:
            raise ValueError(
                f"SESSION_SECRET 长度不足（{len(v)}<{_MIN_SECRET_LEN}）"
            )
        if "replace-with" in v or v.strip() == "change-me":
            raise ValueError("SESSION_SECRET 仍是占位符，请设置为真实随机值")
        return v

    @field_validator("cors_origins")
    @classmethod
    def _no_wildcard(cls, v: str) -> str:
        if any(o.strip() == "*" for o in v.split(",")):
            raise ValueError("CORS_ORIGINS 不能包含 '*'")
        return v

    @property
    def db_path(self) -> Path:
        path = Path(self.portal_db_path)
        if not path.is_absolute():
            path = (Path(__file__).resolve().parent / path).resolve()
        return path

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path.as_posix()}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def trusted_app_list(self) -> list[str]:
        return [a.strip() for a in self.trusted_apps.split(",") if a.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
