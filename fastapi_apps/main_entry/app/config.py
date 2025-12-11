"""Application configuration using Pydantic Settings."""

import os
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings


def get_git_commit() -> str:
    """Get git commit hash - prefer env var, fallback to reading from COMMIT file."""
    # First check environment variable (set by CI/CD)
    if os.environ.get("GIT_COMMIT"):
        return os.environ.get("GIT_COMMIT")
    # Try to read from COMMIT file in common/config
    try:
        # Path: fastapi_apps/main_entry/app/config.py -> common/config/COMMIT
        commit_file = Path(__file__).parent.parent.parent.parent / "common" / "config" / "COMMIT"
        if commit_file.exists():
            commit = commit_file.read_text().strip()
            return commit or "unknown"
    except (OSError, IOError):
        pass
    return "unknown"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "main-entry"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT == "development"

    # Build parameters (set by CI/CD or Makefile)
    BUILD_ID: str = os.environ.get("BUILD_ID", "local")
    BUILD_VERSION: str = os.environ.get("BUILD_VERSION", "0.0.0-dev")
    GIT_COMMIT: str = get_git_commit()

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
