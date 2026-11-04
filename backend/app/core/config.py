from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_env: str = "development"
    # Optional until Phase 2 connects the database.
    database_url: str | None = None
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    # shortcut: shared owner token; customers already use Supabase Auth (ADR 0005), move the
    # owner there with an admin role next. Unset = every admin route answers 401.
    admin_token: str | None = None
    # Email notifications (OPEN_DECISIONS #13). No SMTP host = emails are skipped (logged by
    # subject only), so local dev and tests never send mail.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_starttls: bool = True
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    owner_email: str | None = None  # where "new order awaiting approval" goes
    public_base_url: str = "http://127.0.0.1:8000"  # for links inside emails
    # AI ordering assistant (OPEN_DECISIONS #16: Anthropic Claude). No key = chat answers 503.
    anthropic_api_key: str | None = None
    anthropic_base_url: str | None = None  # local fake for E2E only; unset in real envs
    assistant_model: str = "claude-sonnet-5-5"


@lru_cache
def get_settings() -> Settings:
    return Settings()
