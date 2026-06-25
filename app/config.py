from __future__ import annotations

import warnings

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SP_", extra="ignore")

    # Our database
    database_url: str = "postgresql+asyncpg://shadypredict:shadypredict@localhost:5433/shadypredict"

    # shadybank
    bank_api_url: str = "http://127.0.0.1:8021"
    house_pan: str = "8997000000000002"   # deposits are PUSHed to this card
    house_pin: str = "4242"               # for house login (cash-out, later phases)

    # Security
    fernet_key: str = ""                  # base64 Fernet key for encrypting bank tokens at rest
    session_ttl_seconds: int = 7 * 24 * 3600
    cookie_name: str = "sp_session"
    cookie_secure: bool = False           # True behind HTTPS in prod

    admin_key: str = "dev-admin-key"      # X-Admin-Key header for admin endpoints (set a real one in prod)

    # Betting rules (product decision: NO max bet, NO deposit cap; only a floor)
    min_bet_cents: int = 1000             # 10 ShadyBucks minimum stake

    # Login throttling (we add our own — the bank doesn't rate-limit PIN/password)
    login_max_attempts: int = 8
    login_window_seconds: int = 600

    auto_create_tables: bool = True       # dev convenience; set False in prod (use Alembic)

    env: str = "dev"
    cors_origins: list[str] = ["*"]       # tighten for prod / the UI team's origin


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        s = Settings()
        if not s.fernet_key:
            if s.env != "dev":
                raise RuntimeError("SP_FERNET_KEY is required outside dev")
            from cryptography.fernet import Fernet

            s.fernet_key = Fernet.generate_key().decode()
            warnings.warn("No SP_FERNET_KEY set; generated an ephemeral dev key "
                          "(sessions won't survive a restart).")
        _settings = s
    return _settings
