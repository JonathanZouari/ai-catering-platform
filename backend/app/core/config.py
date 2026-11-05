from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SQLITE_PATH = REPO_ROOT / "data" / "catering.sqlite3"


class Settings(BaseSettings):
    # hide_input_in_errors: a configuration error must not print the secret key.
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), extra="ignore", hide_input_in_errors=True
    )

    app_env: str = "development"
    # SQLite database file. Relative paths resolve from the repository root.
    sqlite_path: Path = DEFAULT_SQLITE_PATH
    # Apply pending migrations on startup (non-destructive; safe to leave on).
    db_auto_migrate: bool = True
    # Where customer orders and the catalog live. Only an explicit "supabase" selects the cloud,
    # and then nothing falls back to SQLite.
    order_database_backend: Literal["sqlite", "supabase"] = "sqlite"
    # Optional cloud staff admin (Database/Auth/Storage).
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    # Server-only secret API key for the customer order RPCs. Never send it to a browser.
    supabase_secret_key: SecretStr | None = None

    @model_validator(mode="after")
    def cloud_orders_are_configured(self) -> Self:
        if self.order_database_backend == "supabase":
            key = self.supabase_secret_key.get_secret_value() if self.supabase_secret_key else ""
            if not (self.supabase_url or "").startswith("https://") or not key.startswith(
                "sb_secret_"
            ):
                raise ValueError(
                    "ORDER_DATABASE_BACKEND=supabase requires an https:// SUPABASE_URL "
                    "and an sb_secret_ SUPABASE_SECRET_KEY"
                )
        return self

    @property
    def sqlite_file(self) -> Path:
        path = self.sqlite_path.expanduser()
        return path if path.is_absolute() else REPO_ROOT / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
