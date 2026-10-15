from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENV: str = "development"
    PORT: int = 8000
    DATABASE_URL: str = "sqlite+aiosqlite:///./acp_dev.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    ACP_PLATFORM_FEE_PCT: float = 0.02
    ACP_MIN_CHECK_INTERVAL_SECONDS: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
