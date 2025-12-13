"""
FastAPI integration for database connection.

Provides dependency injection helpers, lifespan management, and health check endpoints.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncGenerator, Callable, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from fastapi import Depends, FastAPI
except ImportError:
    raise ImportError("FastAPI is required for this module. Install with: pip install fastapi")

from ..config import DatabaseConfig, get_database_config
from ..session import DatabaseManager, get_async_session, get_db_manager


# Type alias for cleaner FastAPI dependency injection
SessionDep = Annotated[AsyncSession, Depends(get_async_session)]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session.

    This is the standard FastAPI pattern using yield for proper cleanup.

    Usage:
        from fastapi import Depends
        from db_connection_postgres.integrations import get_db, SessionDep

        @app.get("/users")
        async def get_users(db: SessionDep):
            # Or: async def get_users(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
            return result.scalars().all()
    """
    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db(config: Optional[DatabaseConfig] = None) -> DatabaseManager:
    """
    Initialize database connection on application startup.

    Args:
        config: Optional custom database configuration.

    Returns:
        DatabaseManager instance.

    Usage in FastAPI:
        @app.on_event("startup")
        async def startup():
            await init_db()
    """
    db_manager = get_db_manager(config)
    # Warm up connection pool by testing connection
    await db_manager.test_connection()
    return db_manager


async def close_db() -> None:
    """
    Close database connections on application shutdown.

    Usage in FastAPI:
        @app.on_event("shutdown")
        async def shutdown():
            await close_db()
    """
    db_manager = get_db_manager()
    await db_manager.dispose()


def create_db_lifespan(
    config: Optional[DatabaseConfig] = None,
) -> Callable[[FastAPI], AsyncGenerator[None, None]]:
    """
    Create a FastAPI lifespan context manager for database connection.

    This is the recommended approach for FastAPI 0.93.0+ instead of
    @app.on_event("startup") and @app.on_event("shutdown").

    Args:
        config: Optional custom database configuration.

    Returns:
        Async context manager function for FastAPI lifespan.

    Usage:
        from fastapi import FastAPI
        from db_connection_postgres.integrations import create_db_lifespan

        lifespan = create_db_lifespan()
        app = FastAPI(lifespan=lifespan)

        # Or with custom config:
        from db_connection_postgres import DatabaseConfig
        config = DatabaseConfig(host="custom-host", port=5433)
        lifespan = create_db_lifespan(config)
        app = FastAPI(lifespan=lifespan)
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # Startup: initialize database
        await init_db(config)
        yield
        # Shutdown: close database connections
        await close_db()

    return lifespan


async def get_health_status() -> dict[str, Any]:
    """
    Get database health status for health check endpoints.

    Returns:
        Dictionary with database health information.

    Usage:
        from fastapi import APIRouter
        from db_connection_postgres.integrations import get_health_status

        router = APIRouter()

        @router.get("/health/db")
        async def health_check():
            return await get_health_status()
    """
    db_manager = get_db_manager()
    config = db_manager.config

    result: dict[str, Any] = {
        "status": "unknown",
        "database": config.database,
        "host": f"{config.host}:{config.port}",
        "pool_size": config.pool_size,
        "max_overflow": config.max_overflow,
    }

    try:
        async with db_manager.async_session() as session:
            # Test basic connectivity
            await session.execute(text("SELECT 1"))

            # Get PostgreSQL version
            version_result = await session.execute(text("SELECT version()"))
            version = version_result.scalar()

            result["status"] = "healthy"
            result["pg_version"] = version

            # Get connection pool stats if available
            engine = db_manager.async_engine
            pool = engine.pool
            if hasattr(pool, "status"):
                result["pool_status"] = pool.status()

    except Exception as e:
        result["status"] = "unhealthy"
        result["error"] = str(e)

    return result
