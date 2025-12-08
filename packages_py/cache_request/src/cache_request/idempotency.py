"""
Idempotency key management for HTTP requests.
"""
import hashlib
import time
import uuid
from typing import Callable, Optional, Set, TypeVar

from .types import (
    IdempotencyConfig,
    CacheRequestStore,
    StoredResponse,
    IdempotencyCheckResult,
    RequestFingerprint,
    CacheRequestEvent,
    CacheRequestEventType,
    CacheRequestEventListener,
)
from .stores.memory import MemoryCacheStore

T = TypeVar("T")


def _default_key_generator() -> str:
    """Default key generator using UUID4."""
    return str(uuid.uuid4())


DEFAULT_IDEMPOTENCY_CONFIG = IdempotencyConfig(
    header_name="Idempotency-Key",
    ttl_seconds=86400,  # 24 hours
    auto_generate=True,
    methods=["POST", "PATCH"],
    key_generator=_default_key_generator,
)


def merge_idempotency_config(
    config: Optional[IdempotencyConfig] = None,
) -> IdempotencyConfig:
    """Merge user config with defaults."""
    if config is None:
        return IdempotencyConfig(
            header_name=DEFAULT_IDEMPOTENCY_CONFIG.header_name,
            ttl_seconds=DEFAULT_IDEMPOTENCY_CONFIG.ttl_seconds,
            auto_generate=DEFAULT_IDEMPOTENCY_CONFIG.auto_generate,
            methods=list(DEFAULT_IDEMPOTENCY_CONFIG.methods),
            key_generator=DEFAULT_IDEMPOTENCY_CONFIG.key_generator,
        )

    return IdempotencyConfig(
        header_name=config.header_name or DEFAULT_IDEMPOTENCY_CONFIG.header_name,
        ttl_seconds=config.ttl_seconds
        if config.ttl_seconds is not None
        else DEFAULT_IDEMPOTENCY_CONFIG.ttl_seconds,
        auto_generate=config.auto_generate
        if config.auto_generate is not None
        else DEFAULT_IDEMPOTENCY_CONFIG.auto_generate,
        methods=config.methods if config.methods else list(DEFAULT_IDEMPOTENCY_CONFIG.methods),
        key_generator=config.key_generator or DEFAULT_IDEMPOTENCY_CONFIG.key_generator,
    )


def generate_fingerprint(request: RequestFingerprint) -> str:
    """Generate a request fingerprint for validation."""
    parts = [request.method, request.url]

    if request.body:
        body_str = request.body.decode("utf-8", errors="replace")
        parts.append(body_str)

    return "|".join(parts)


class IdempotencyConflictError(Exception):
    """Error thrown when an idempotency key conflict occurs."""

    code = "IDEMPOTENCY_CONFLICT"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.name = "IdempotencyConflictError"


class IdempotencyManager:
    """
    IdempotencyManager - Manages idempotency keys and cached responses.

    For mutating operations (POST, PATCH), ensures that:
    1. Each request intent is processed exactly once
    2. Retries use the same idempotency key
    3. Duplicate requests return cached responses

    Example:
        manager = IdempotencyManager(IdempotencyConfig(ttl_seconds=3600))

        # Check for cached response
        check = await manager.check("my-key")
        if check.cached:
            return check.response.value

        # Execute request and store response
        response = await http_client.post(url)
        await manager.store(check.key, response)
    """

    def __init__(
        self,
        config: Optional[IdempotencyConfig] = None,
        store: Optional[CacheRequestStore] = None,
    ) -> None:
        self._config = merge_idempotency_config(config)
        self._store = store or MemoryCacheStore()
        self._listeners: Set[CacheRequestEventListener] = set()

    def generate_key(self) -> str:
        """Generate a new idempotency key."""
        generator = self._config.key_generator or _default_key_generator
        return generator()

    def requires_idempotency(self, method: str) -> bool:
        """Check if a request method requires idempotency."""
        return method.upper() in self._config.methods

    async def check(
        self,
        key: str,
        fingerprint: Optional[RequestFingerprint] = None,
    ) -> IdempotencyCheckResult:
        """Check for a cached response by idempotency key."""
        response = await self._store.get(key)

        if response:
            # Validate fingerprint if provided
            if fingerprint and response.fingerprint:
                current_fingerprint = generate_fingerprint(fingerprint)
                if current_fingerprint != response.fingerprint:
                    raise IdempotencyConflictError(
                        f"Idempotency key '{key}' is already associated with a different request"
                    )

            self._emit(
                CacheRequestEvent(
                    type=CacheRequestEventType.IDEMPOTENCY_HIT,
                    key=key,
                    timestamp=time.time(),
                    metadata={"cached_at": response.cached_at},
                )
            )

            return IdempotencyCheckResult(cached=True, key=key, response=response)

        self._emit(
            CacheRequestEvent(
                type=CacheRequestEventType.IDEMPOTENCY_MISS,
                key=key,
                timestamp=time.time(),
            )
        )

        return IdempotencyCheckResult(cached=False, key=key)

    async def store(
        self,
        key: str,
        value: T,
        fingerprint: Optional[RequestFingerprint] = None,
    ) -> None:
        """Store a response with an idempotency key."""
        now = time.time()
        response = StoredResponse(
            value=value,
            cached_at=now,
            expires_at=now + self._config.ttl_seconds,
            fingerprint=generate_fingerprint(fingerprint) if fingerprint else None,
        )

        await self._store.set(key, response)

        self._emit(
            CacheRequestEvent(
                type=CacheRequestEventType.IDEMPOTENCY_STORE,
                key=key,
                timestamp=now,
                metadata={"expires_at": response.expires_at},
            )
        )

    async def invalidate(self, key: str) -> bool:
        """Invalidate a cached response."""
        deleted = await self._store.delete(key)

        if deleted:
            self._emit(
                CacheRequestEvent(
                    type=CacheRequestEventType.IDEMPOTENCY_EXPIRE,
                    key=key,
                    timestamp=time.time(),
                )
            )

        return deleted

    def get_header_name(self) -> str:
        """Get the idempotency header name."""
        return self._config.header_name

    def get_config(self) -> IdempotencyConfig:
        """Get configuration."""
        return self._config

    async def get_stats(self) -> dict:
        """Get store statistics."""
        return {"size": await self._store.size()}

    def on(self, listener: CacheRequestEventListener) -> Callable[[], None]:
        """Add event listener."""
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def off(self, listener: CacheRequestEventListener) -> None:
        """Remove event listener."""
        self._listeners.discard(listener)

    def _emit(self, event: CacheRequestEvent) -> None:
        """Emit an event to all listeners."""
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass  # Ignore listener errors

    async def close(self) -> None:
        """Close the manager and release resources."""
        await self._store.close()
        self._listeners.clear()


def create_idempotency_manager(
    config: Optional[IdempotencyConfig] = None,
    store: Optional[CacheRequestStore] = None,
) -> IdempotencyManager:
    """Create an idempotency manager."""
    return IdempotencyManager(config, store)
