"""Application configuration using Pydantic Settings."""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "hello-fastapi"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT == "development"

    # Server
    HOST: str = os.environ.get("HOST", "0.0.0.0")
    PORT: int = int(os.environ.get("PORT", "52000"))

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:51000",
        "http://localhost:52000",
        "http://localhost:5173",
    ]

    class Config:
        case_sensitive = True
        env_file = None  # Use system env only


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
