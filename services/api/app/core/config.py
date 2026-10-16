import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ROOT_ENV = BASE_DIR.parent.parent / ".env"
LOCAL_ENV = BASE_DIR / ".env"

class Settings(BaseSettings):
    ENV: str = "development"
    PORT: int = 8000
    DATABASE_URL: str = "sqlite+aiosqlite:///./acp_dev.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    ACP_PLATFORM_FEE_PCT: float = 0.02
    ACP_MIN_CHECK_INTERVAL_SECONDS: int = 60
    ASAAS_API_KEY: str = ""
    ASAAS_BASE_URL: str = "https://api.asaas.com/v3"
    ASAAS_WEBHOOK_ACCESS_TOKEN: str = ""
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_TIMEOUT_SECONDS: int = 45

    model_config = SettingsConfigDict(
        env_file=(str(LOCAL_ENV), str(ROOT_ENV), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

def get_settings() -> Settings:
    return Settings()

settings = get_settings()

