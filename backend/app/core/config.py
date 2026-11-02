from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SQLITE_PATH = Path(__file__).resolve().parents[3] / "database" / "catering.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_env: str = "development"
    sqlite_path: Path = DEFAULT_SQLITE_PATH
    # Supabase settings: not used while the app runs on SQLite.
    database_url: str | None = None
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
