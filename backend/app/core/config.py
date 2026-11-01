from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_env: Literal["development", "staging", "production"] = "development"
    # Optional so /health and static pages work without a database.
    database_url: str | None = None
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    anthropic_api_key: str | None = None
    ai_model: str = "claude-sonnet-5-5"
    ai_monthly_message_limit: int = 1000

    @property
    def is_deployed(self) -> bool:
        return self.app_env in ("staging", "production")

    def require_deployment_settings(self) -> None:
        """Fails at startup, so a misconfigured server never takes traffic. Names only."""
        if not self.is_deployed:
            return
        required = {
            "DATABASE_URL": self.database_url,
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_ANON_KEY": self.supabase_anon_key,
            "SUPABASE_SERVICE_ROLE_KEY": self.supabase_service_role_key,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"Missing settings: {', '.join(missing)}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
