from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

# 会话密钥最小长度（字节）。secrets.token_hex(32) 输出 64 字符，
# secrets.token_urlsafe(32) 输出 ~43 字符；32 字节熵足够。
_MIN_SECRET_LEN = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    pmo_db_path: str = str(ROOT / "data" / "innogreen_pmo.db")
    # 会话签名密钥（必填：未设或长度不足则 Settings 校验失败、应用拒绝启动——刻意的安全闸）
    pmo_session_secret: str
    # 首个管理员引导种子（仅 users 表为空时生效，用于冷启动建一号管理员）
    pmo_bootstrap_admin_username: str | None = None
    pmo_bootstrap_admin_password: str | None = None
    pmo_host: str = "127.0.0.1"
    pmo_port: int = 8000
    # API 文档（/docs、/redoc）默认关闭：Swagger 暴露完整 schema 与字段名（含 password），
    # 生产环境是信息泄露面。开发需显式设 PMO_ENABLE_DOCS=true 开启。
    pmo_enable_docs: bool = False
    pmo_cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    # 会话 cookie 是否仅 HTTPS（生产 HTTPS 反代后设 true）
    pmo_https_only: bool = False
    # 会话 cookie 名（须与 Portal SESSION_COOKIE_NAME 一致，同域 SSO）
    pmo_session_cookie_name: str = "innogreen_session"
    # 可选：跨子域共享时设为 .example.com；同域路径路由请留空
    pmo_session_cookie_domain: str = ""
    # 公网路径前缀（同域 nginx /pmo/ 部署时设为 /pmo；本地开发留空）
    pmo_public_base: str = ""
    # 是否信任代理头解析真实 IP（X-Forwarded-For / CF-Connecting-IP）。
    # 默认 false：直接对外时客户端可伪造 XFF 绕过 IP 限速。
    # 仅在可信反向代理（nginx / Cloudflare Tunnel）后设 true。
    pmo_trust_proxy_header: bool = False
    # qcc 企业资质库路径（用于方案一：直接 ATTACH qcc 数据库只读查询）
    # 同机部署时设为 qcc 的 data/qualifications.db 绝对路径，留空则禁用 qcc 关联功能
    pmo_qcc_db_path: str = ""
    # 统一认证 Portal 基址。非空则启用 SSO：登录/验会话走 Portal（须与 Portal 共用同一会话密钥）。
    # 例：http://127.0.0.1:8001 ；留空则使用本地 users 表（pytest / 单机兜底）。
    pmo_portal_base_url: str = ""
    # Portal 前端入口（登录页提示/跳转用；可与 API 同域不同路径）
    pmo_portal_web_url: str = ""

    @field_validator("pmo_session_secret")
    @classmethod
    def _strong_session_secret(cls, v: str) -> str:
        # 拒绝弱 / 占位密钥。运维误贴短串或示例占位会让签名 cookie 可被伪造。
        if len(v) < _MIN_SECRET_LEN:
            raise ValueError(
                f"PMO_SESSION_SECRET 长度不足（{len(v)}<{_MIN_SECRET_LEN}）。"
                "请用 `python -c \"import secrets; print(secrets.token_hex(32))` 生成。"
            )
        if "replace-with-output-of" in v or v.strip() == "change-me":
            raise ValueError(
                "PMO_SESSION_SECRET 仍是 .env.example 的占位符，请替换为真实随机值。"
            )
        return v

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
