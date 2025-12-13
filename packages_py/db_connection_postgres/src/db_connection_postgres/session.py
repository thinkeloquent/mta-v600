"""
Database session management module.

Provides async and sync session factories with proper lifecycle management.
Implements the yield pattern for FastAPI dependency injection.
"""
from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import DatabaseConfig, get_database_config


class DatabaseManager:
    """
    Manages database engine and session factory lifecycle.

    Supports both async (asyncpg) and sync (psycopg2) connections.
    """

    def __init__(self, config: Optional[DatabaseConfig] = None) -> None:
        """
        Initialize database manager.

        Args:
            config: Database configuration. If None, reads from environment.
        """
        self._config = config or get_database_config()
        self._async_engine: Optional[AsyncEngine] = None
        self._sync_engine: Optional[object] = None
        self._async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._sync_session_factory: Optional[sessionmaker] = None

    @property
    def config(self) -> DatabaseConfig:
        """Get database configuration."""
        return self._config

    @property
    def async_engine(self) -> AsyncEngine:
        """Get or create async engine."""
        if self._async_engine is None:
            self._async_engine = create_async_engine(
                self._config.get_async_url(),
                connect_args=self._config.get_connect_args(),
                **self._config.get_engine_kwargs(),
            )
        return self._async_engine

    @property
    def sync_engine(self):
        """Get or create sync engine."""
        if self._sync_engine is None:
            self._sync_engine = create_engine(
                self._config.get_sync_url(),
                pool_size=self._config.pool_size,
                max_overflow=self._config.max_overflow,
                pool_timeout=self._config.pool_timeout,
                pool_recycle=self._config.pool_recycle,
                pool_pre_ping=True,
                echo=self._config.echo,
            )
        return self._sync_engine

    @property
    def async_session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get or create async session factory."""
        if self._async_session_factory is None:
            self._async_session_factory = async_sessionmaker(
                bind=self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )
        return self._async_session_factory

    @property
    def sync_session_factory(self) -> sessionmaker:
        """Get or create sync session factory."""
        if self._sync_session_factory is None:
            self._sync_session_factory = sessionmaker(
                bind=self.sync_engine,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )
        return self._sync_session_factory

    @asynccontextmanager
    async def async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Async context manager for database sessions.

        Usage:
            async with db_manager.async_session() as session:
                result = await session.execute(select(User))
        """
        session = self.async_session_factory()
        try:
            yield session
        finally:
            await session.close()

    @contextmanager
    def sync_session(self) -> Generator[Session, None, None]:
        """
        Sync context manager for database sessions.

        Usage:
            with db_manager.sync_session() as session:
                result = session.execute(select(User))
        """
        session = self.sync_session_factory()
        try:
            yield session
        finally:
            session.close()

    async def dispose_async(self) -> None:
        """Dispose async engine connections."""
        if self._async_engine is not None:
            await self._async_engine.dispose()
            self._async_engine = None
            self._async_session_factory = None

    def dispose_sync(self) -> None:
        """Dispose sync engine connections."""
        if self._sync_engine is not None:
            self._sync_engine.dispose()
            self._sync_engine = None
            self._sync_session_factory = None

    async def dispose(self) -> None:
        """Dispose all engine connections."""
        await self.dispose_async()
        self.dispose_sync()

    async def test_connection(self) -> bool:
        """Test async database connection."""
        from sqlalchemy import text

        try:
            async with self.async_session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def test_sync_connection(self) -> bool:
        """Test sync database connection."""
        from sqlalchemy import text

        try:
            with self.sync_session() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False


# Global database manager instance (lazy initialization)
_db_manager: Optional[DatabaseManager] = None


def get_db_manager(config: Optional[DatabaseConfig] = None) -> DatabaseManager:
    """
    Get or create global database manager.

    Args:
        config: Optional custom configuration. If provided on first call,
                sets the configuration for the global instance.

    Returns:
        Global DatabaseManager instance.
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(config)
    return _db_manager


def reset_db_manager() -> None:
    """Reset global database manager (useful for testing)."""
    global _db_manager
    _db_manager = None


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async session generator for dependency injection.

    This is the standard FastAPI dependency pattern using yield.

    Usage in FastAPI:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_async_session)):
            result = await db.execute(select(User))
            return result.scalars().all()
    """
    db_manager = get_db_manager()
    async with db_manager.async_session() as session:
        try:
            yield session
        finally:
            await session.close()


def get_sync_session() -> Generator[Session, None, None]:
    """
    Sync session generator for dependency injection.

    Usage:
        def get_users(db: Session = Depends(get_sync_session)):
            result = db.execute(select(User))
            return result.scalars().all()
    """
    db_manager = get_db_manager()
    with db_manager.sync_session() as session:
        try:
            yield session
        finally:
            session.close()
