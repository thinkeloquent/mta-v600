"""Pytest configuration and fixtures for cache_request tests."""
import asyncio
import pytest
from typing import AsyncGenerator, Generator

from cache_request import (
    MemoryCacheStore,
    MemorySingleflightStore,
    IdempotencyManager,
    Singleflight,
)


@pytest.fixture
def memory_cache_store() -> Generator[MemoryCacheStore, None, None]:
    """Create a memory cache store for testing."""
    store = MemoryCacheStore(cleanup_interval_seconds=60.0)
    yield store


@pytest.fixture
def memory_singleflight_store() -> MemorySingleflightStore:
    """Create a memory singleflight store for testing."""
    return MemorySingleflightStore()


@pytest.fixture
async def idempotency_manager(
    memory_cache_store: MemoryCacheStore,
) -> AsyncGenerator[IdempotencyManager, None]:
    """Create an idempotency manager for testing."""
    manager = IdempotencyManager(store=memory_cache_store)
    yield manager
    await manager.close()


@pytest.fixture
def singleflight(
    memory_singleflight_store: MemorySingleflightStore,
) -> Generator[Singleflight, None, None]:
    """Create a singleflight instance for testing."""
    sf = Singleflight(store=memory_singleflight_store)
    yield sf
    sf.close()
