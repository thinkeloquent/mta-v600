"""
Request coalescing (Singleflight) implementation.

When multiple identical requests are made concurrently, only one
actually executes - others wait and receive the same result.
"""
import asyncio
import hashlib
import time
from typing import Awaitable, Callable, Optional, Set, TypeVar

from .types import (
    SingleflightConfig,
    SingleflightStore,
    InFlightRequest,
    RequestFingerprint,
    SingleflightResult,
    CacheRequestEvent,
    CacheRequestEventType,
    CacheRequestEventListener,
)
from .stores.memory import MemorySingleflightStore

T = TypeVar("T")


def _default_fingerprint_generator(request: RequestFingerprint) -> str:
    """Default fingerprint generator using SHA-256."""
    hasher = hashlib.sha256()
    hasher.update(request.method.encode())
    hasher.update(request.url.encode())

    if request.body:
        hasher.update(request.body)

    if request.headers:
        sorted_headers = "|".join(
            f"{k}:{v}" for k, v in sorted(request.headers.items())
        )
        hasher.update(sorted_headers.encode())

    return hasher.hexdigest()


DEFAULT_SINGLEFLIGHT_CONFIG = SingleflightConfig(
    ttl_seconds=30,  # 30 seconds
    methods=["GET", "HEAD"],
    fingerprint_generator=_default_fingerprint_generator,
    include_headers=False,
    header_keys=[],
)


def merge_singleflight_config(
    config: Optional[SingleflightConfig] = None,
) -> SingleflightConfig:
    """Merge user config with defaults."""
    if config is None:
        return SingleflightConfig(
            ttl_seconds=DEFAULT_SINGLEFLIGHT_CONFIG.ttl_seconds,
            methods=list(DEFAULT_SINGLEFLIGHT_CONFIG.methods),
            fingerprint_generator=DEFAULT_SINGLEFLIGHT_CONFIG.fingerprint_generator,
            include_headers=DEFAULT_SINGLEFLIGHT_CONFIG.include_headers,
            header_keys=list(DEFAULT_SINGLEFLIGHT_CONFIG.header_keys),
        )

    return SingleflightConfig(
        ttl_seconds=config.ttl_seconds
        if config.ttl_seconds is not None
        else DEFAULT_SINGLEFLIGHT_CONFIG.ttl_seconds,
        methods=config.methods if config.methods else list(DEFAULT_SINGLEFLIGHT_CONFIG.methods),
        fingerprint_generator=config.fingerprint_generator
        or DEFAULT_SINGLEFLIGHT_CONFIG.fingerprint_generator,
        include_headers=config.include_headers
        if config.include_headers is not None
        else DEFAULT_SINGLEFLIGHT_CONFIG.include_headers,
        header_keys=config.header_keys
        if config.header_keys
        else list(DEFAULT_SINGLEFLIGHT_CONFIG.header_keys),
    )


class Singleflight:
    """
    Singleflight - Request coalescing for concurrent identical requests.

    Implements the "singleflight" pattern (popularized by Go's sync/singleflight):
    When multiple goroutines/tasks request the same resource simultaneously,
    only one request is made and the result is shared with all waiters.

    Example:
        sf = Singleflight()

        # These 50 concurrent calls result in only 1 actual fetch
        async def fetch_data():
            return await sf.do(
                RequestFingerprint(method="GET", url="/api/data"),
                lambda: http_client.get("/api/data")
            )

        results = await asyncio.gather(*[fetch_data() for _ in range(50)])

        # All 50 results are identical
        print(results[0].shared)  # False (the leader)
        print(results[1].shared)  # True (joined existing)
    """

    def __init__(
        self,
        config: Optional[SingleflightConfig] = None,
        store: Optional[SingleflightStore] = None,
    ) -> None:
        self._config = merge_singleflight_config(config)
        self._store = store or MemorySingleflightStore()
        self._listeners: Set[CacheRequestEventListener] = set()

    def supports_coalescing(self, method: str) -> bool:
        """Check if a request method supports coalescing."""
        return method.upper() in self._config.methods

    def generate_fingerprint(self, request: RequestFingerprint) -> str:
        """Generate a fingerprint for a request."""
        # Filter headers if needed
        filtered_request = request

        if self._config.include_headers and request.headers:
            filtered_headers = {}
            for key in self._config.header_keys:
                lower_key = key.lower()
                for k, v in request.headers.items():
                    if k.lower() == lower_key:
                        filtered_headers[k] = v
            filtered_request = RequestFingerprint(
                method=request.method,
                url=request.url,
                headers=filtered_headers,
                body=request.body,
            )
        elif not self._config.include_headers:
            filtered_request = RequestFingerprint(
                method=request.method,
                url=request.url,
                headers=None,
                body=request.body,
            )

        generator = self._config.fingerprint_generator or _default_fingerprint_generator
        return generator(filtered_request)

    async def do(
        self,
        request: RequestFingerprint,
        fn: Callable[[], Awaitable[T]],
    ) -> SingleflightResult[T]:
        """
        Execute a function with request coalescing.

        If an identical request is already in-flight, wait for it and share the result.
        Otherwise, execute the function and share the result with any subsequent waiters.
        """
        fingerprint = self.generate_fingerprint(request)

        # Check for in-flight request
        existing = self._store.get(fingerprint)
        if existing:
            existing.subscribers += 1

            self._emit(
                CacheRequestEvent(
                    type=CacheRequestEventType.SINGLEFLIGHT_JOIN,
                    key=fingerprint,
                    timestamp=time.time(),
                    metadata={"subscribers": existing.subscribers},
                )
            )

            try:
                value = await existing.future
                return SingleflightResult(
                    value=value,
                    shared=True,
                    subscribers=existing.subscribers,
                )
            except Exception:
                raise

        # Create new in-flight request
        loop = asyncio.get_event_loop()
        future: asyncio.Future[T] = loop.create_future()

        in_flight = InFlightRequest(
            future=future,
            subscribers=1,
            started_at=time.time(),
        )

        self._store.set(fingerprint, in_flight)

        self._emit(
            CacheRequestEvent(
                type=CacheRequestEventType.SINGLEFLIGHT_LEAD,
                key=fingerprint,
                timestamp=time.time(),
            )
        )

        try:
            value = await fn()

            future.set_result(value)

            current = self._store.get(fingerprint)
            final_subscribers = current.subscribers if current else 1

            self._emit(
                CacheRequestEvent(
                    type=CacheRequestEventType.SINGLEFLIGHT_COMPLETE,
                    key=fingerprint,
                    timestamp=time.time(),
                    metadata={
                        "subscribers": final_subscribers,
                        "duration_seconds": time.time() - in_flight.started_at,
                    },
                )
            )

            self._store.delete(fingerprint)

            return SingleflightResult(
                value=value,
                shared=False,
                subscribers=final_subscribers,
            )

        except Exception as error:
            future.set_exception(error)

            self._emit(
                CacheRequestEvent(
                    type=CacheRequestEventType.SINGLEFLIGHT_ERROR,
                    key=fingerprint,
                    timestamp=time.time(),
                    metadata={"error": str(error)},
                )
            )

            self._store.delete(fingerprint)

            raise

    def is_in_flight(self, request: RequestFingerprint) -> bool:
        """Check if a request is currently in-flight."""
        fingerprint = self.generate_fingerprint(request)
        return self._store.has(fingerprint)

    def get_subscribers(self, request: RequestFingerprint) -> int:
        """Get the number of subscribers for an in-flight request."""
        fingerprint = self.generate_fingerprint(request)
        existing = self._store.get(fingerprint)
        return existing.subscribers if existing else 0

    def get_stats(self) -> dict:
        """Get statistics about in-flight requests."""
        return {"in_flight": self._store.size()}

    def get_config(self) -> SingleflightConfig:
        """Get configuration."""
        return self._config

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

    def clear(self) -> None:
        """Clear all in-flight requests (use with caution)."""
        self._store.clear()

    def close(self) -> None:
        """Close and release resources."""
        self._store.clear()
        self._listeners.clear()


def create_singleflight(
    config: Optional[SingleflightConfig] = None,
    store: Optional[SingleflightStore] = None,
) -> Singleflight:
    """Create a singleflight instance."""
    return Singleflight(config, store)
