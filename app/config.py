from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///actly.db"
    secret_key: str = "change-me-in-production"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    base_url: str = "http://localhost:8000"
    new_agent_credits: float = 10.0
    eth_usd_price: float = 2000.0  # Used for crypto deposits

    class Config:
        env_file = ".env"
        extra = "allow"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def get_database_url() -> str:
    """Rewrite postgresql:// → postgresql+asyncpg:// for asyncpg compatibility."""
    url = os.getenv("DATABASE_URL", get_settings().database_url)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url
