from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SQLITE_PATH = REPO_ROOT / "data" / "catering.sqlite3"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_env: str = "development"
    # SQLite database file. Relative paths resolve from the repository root.
    sqlite_path: Path = DEFAULT_SQLITE_PATH
    # Apply pending migrations on startup (non-destructive; safe to leave on).
    db_auto_migrate: bool = True
    # Supabase Storage/Auth only (optional). The database is SQLite: see docs/ADR/0005.
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None

    @property
    def sqlite_file(self) -> Path:
        path = self.sqlite_path.expanduser()
        return path if path.is_absolute() else REPO_ROOT / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
