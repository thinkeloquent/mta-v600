"""
Database configuration module.

Reads PostgreSQL connection parameters from environment variables and builds
SQLAlchemy URL objects using the URL.create() pattern for safety.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import URL


@dataclass
class DatabaseConfig:
    """PostgreSQL database configuration from environment variables."""

    host: str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    user: str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "postgres"))
    password: str = field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", "postgres"))
    database: str = field(default_factory=lambda: os.getenv("POSTGRES_DB", "postgres"))
    schema: str = field(default_factory=lambda: os.getenv("POSTGRES_SCHEMA", "public"))

    # Connection pool settings
    pool_size: int = field(default_factory=lambda: int(os.getenv("POSTGRES_POOL_SIZE", "5")))
    max_overflow: int = field(
        default_factory=lambda: int(os.getenv("POSTGRES_MAX_OVERFLOW", "10"))
    )
    pool_timeout: int = field(
        default_factory=lambda: int(os.getenv("POSTGRES_POOL_TIMEOUT", "30"))
    )
    pool_recycle: int = field(
        default_factory=lambda: int(os.getenv("POSTGRES_POOL_RECYCLE", "1800"))
    )

    # SSL settings
    ssl_mode: str = field(default_factory=lambda: os.getenv("POSTGRES_SSL_MODE", "disable"))

    # Echo SQL statements (for debugging)
    echo: bool = field(
        default_factory=lambda: os.getenv("POSTGRES_ECHO", "false").lower() == "true"
    )

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.host:
            self.host = "localhost"
        if self.port <= 0:
            self.port = 5432

    def get_async_url(self) -> URL:
        """Build async SQLAlchemy URL using asyncpg driver."""
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
        )

    def get_sync_url(self) -> URL:
        """Build sync SQLAlchemy URL using psycopg2 driver."""
        return URL.create(
            drivername="postgresql+psycopg2",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
        )

    def get_async_url_string(self, hide_password: bool = True) -> str:
        """Get async URL as string, optionally hiding password."""
        return self.get_async_url().render_as_string(hide_password=hide_password)

    def get_sync_url_string(self, hide_password: bool = True) -> str:
        """Get sync URL as string, optionally hiding password."""
        return self.get_sync_url().render_as_string(hide_password=hide_password)

    def get_connect_args(self) -> dict[str, Any]:
        """Get connection arguments for asyncpg driver."""
        args: dict[str, Any] = {}

        # SSL configuration for asyncpg
        if self.ssl_mode == "disable":
            args["ssl"] = "disable"
        elif self.ssl_mode in ("require", "verify-ca", "verify-full"):
            args["ssl"] = self.ssl_mode

        return args

    def get_engine_kwargs(self) -> dict[str, Any]:
        """Get keyword arguments for create_async_engine."""
        return {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "pool_pre_ping": True,  # Enable connection health check
            "echo": self.echo,
        }


def get_database_config() -> DatabaseConfig:
    """Factory function to create DatabaseConfig from environment."""
    return DatabaseConfig()


def get_database_url() -> str:
    """Get async database URL string (for backward compatibility)."""
    config = get_database_config()
    return config.get_async_url_string(hide_password=False)


def get_sync_database_url() -> str:
    """Get sync database URL string (for Alembic migrations)."""
    config = get_database_config()
    return config.get_sync_url_string(hide_password=False)
