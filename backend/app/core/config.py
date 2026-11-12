from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_env: str = "development"
    # Empty locally to use the SQLite file (app/core/database.py).
    database_url: str | None = None
    supabase_url: str | None = None
    # Safe in the browser; access is limited by RLS.
    supabase_publishable_key: str | None = None
    # Server-side only (Storage uploads, Auth admin). Never sent to the browser or committed.
    supabase_secret_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
