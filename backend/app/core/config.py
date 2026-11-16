from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_env: str = "development"
    # Optional until Phase 2 connects the database.
    database_url: str | None = None
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    # Bearer token for admin-only endpoints (leads hold personal data); needed outside development.
    admin_api_token: str | None = None
    # Customers+orders export used by the lead scoring service until leads live in the database.
    leads_data_path: str = str(
        Path(__file__).resolve().parents[3] / "data" / "combined_clients_orders.csv"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
