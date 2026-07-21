from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    pmo_db_path: str = str(ROOT / "data" / "innogreen_pmo.db")
    pmo_api_token: str = "dev-token-change-me"
    pmo_host: str = "127.0.0.1"
    pmo_port: int = 8000
    pmo_enable_docs: bool = True
    pmo_cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.pmo_cors_origins.split(",") if o.strip()]

    @property
    def db_url(self) -> str:
        path = Path(self.pmo_db_path)
        if not path.is_absolute():
            path = (Path(__file__).resolve().parents[1] / path).resolve()
        return f"sqlite:///{path.as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
