"""
Configuration module.

Reads all settings from environment variables (or .env file).
Using pydantic-settings means every config value is type-checked at startup.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Gemini
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.0-flash-001"

    # Postgres
    POSTGRES_USER: str = "conductor"
    POSTGRES_PASSWORD: str = "conductor_pass"
    POSTGRES_DB: str = "conductor_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # App
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def POSTGRES_URL(self) -> str:
        """SQLAlchemy-compatible connection string."""
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def POSTGRES_URL_SYNC(self) -> str:
        """psycopg (v3) sync DSN for LangGraph checkpointer."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache()
def get_settings() -> Settings:
    """Returns cached settings instance. Call this everywhere instead of instantiating directly."""
    return Settings()


settings = get_settings()
