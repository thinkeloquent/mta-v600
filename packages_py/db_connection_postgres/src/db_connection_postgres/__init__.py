"""
PostgreSQL database connection package using SQLAlchemy 2.0 and asyncpg.

This package provides a modern, async-first database connection layer for Python
applications using SQLAlchemy 2.0 patterns with asyncpg driver.

Features:
- SQLAlchemy 2.0 syntax with Mapped[] and mapped_column()
- Async-first design using asyncpg driver
- FastAPI integration with dependency injection
- Connection pooling with health checks
- Environment-based configuration
- Type-safe database models

Quick Start:

    # Basic usage with FastAPI
    from fastapi import FastAPI
    from db_connection_postgres import Base, SessionDep, create_db_lifespan
    from db_connection_postgres.types import IntPrimaryKeyMixin, TimestampMixin
    from sqlalchemy import select
    from sqlalchemy.orm import Mapped, mapped_column

    # Define your model
    class User(Base, IntPrimaryKeyMixin, TimestampMixin):
        __tablename__ = "users"

        email: Mapped[str] = mapped_column(unique=True, index=True)
        is_active: Mapped[bool] = mapped_column(default=True)

    # Create FastAPI app with database lifespan
    lifespan = create_db_lifespan()
    app = FastAPI(lifespan=lifespan)

    @app.get("/users")
    async def get_users(db: SessionDep):
        result = await db.execute(select(User).limit(10))
        return result.scalars().all()

Environment Variables:
    POSTGRES_HOST: Database host (default: localhost)
    POSTGRES_PORT: Database port (default: 5432)
    POSTGRES_USER: Database user (default: postgres)
    POSTGRES_PASSWORD: Database password (default: postgres)
    POSTGRES_DB: Database name (default: postgres)
    POSTGRES_SCHEMA: Database schema (default: public)
    POSTGRES_POOL_SIZE: Connection pool size (default: 5)
    POSTGRES_MAX_OVERFLOW: Max overflow connections (default: 10)
    POSTGRES_SSL_MODE: SSL mode (default: disable)
    POSTGRES_ECHO: Echo SQL statements (default: false)
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, Mapped, mapped_column

# Configuration
from .config import (
    DatabaseConfig,
    get_database_config,
    get_database_url,
    get_sync_database_url,
)

# Session management
from .session import (
    DatabaseManager,
    get_db_manager,
    reset_db_manager,
    get_async_session,
    get_sync_session,
)

# Types and base classes
from .types import (
    Base,
    TimestampMixin,
    SoftDeleteMixin,
    UUIDPrimaryKeyMixin,
    IntPrimaryKeyMixin,
    TableNameMixin,
    IntPK,
    UUIDPK,
    str_50,
    str_100,
    str_255,
    str_500,
    create_base_model,
)

# FastAPI integration (lazy import to avoid requiring FastAPI)
def _get_fastapi_deps():
    """Lazy import FastAPI dependencies."""
    from .integrations.fastapi import (
        SessionDep,
        get_db,
        init_db,
        close_db,
        create_db_lifespan,
        get_health_status,
    )
    return SessionDep, get_db, init_db, close_db, create_db_lifespan, get_health_status


# For backwards compatibility and convenience
try:
    from .integrations.fastapi import (
        SessionDep,
        get_db,
        init_db,
        close_db,
        create_db_lifespan,
        get_health_status,
    )
except ImportError:
    # FastAPI not installed - these will be None
    SessionDep = None  # type: ignore
    get_db = None  # type: ignore
    init_db = None  # type: ignore
    close_db = None  # type: ignore
    create_db_lifespan = None  # type: ignore
    get_health_status = None  # type: ignore


__all__ = [
    # SQLAlchemy re-exports
    "AsyncSession",
    "Session",
    "Mapped",
    "mapped_column",
    # Configuration
    "DatabaseConfig",
    "get_database_config",
    "get_database_url",
    "get_sync_database_url",
    # Session management
    "DatabaseManager",
    "get_db_manager",
    "reset_db_manager",
    "get_async_session",
    "get_sync_session",
    # Types and base classes
    "Base",
    "TimestampMixin",
    "SoftDeleteMixin",
    "UUIDPrimaryKeyMixin",
    "IntPrimaryKeyMixin",
    "TableNameMixin",
    "IntPK",
    "UUIDPK",
    "str_50",
    "str_100",
    "str_255",
    "str_500",
    "create_base_model",
    # FastAPI integration
    "SessionDep",
    "get_db",
    "init_db",
    "close_db",
    "create_db_lifespan",
    "get_health_status",
]

__version__ = "1.0.0"
