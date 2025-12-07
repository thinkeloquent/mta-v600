"""
Rate limiter transport wrapper for httpx
"""
import asyncio
import time
from typing import Optional, Any
from email.utils import parsedate_to_datetime

import httpx

from fetch_rate_limiter import (
    RateLimiter,
    RateLimiterConfig,
    StaticRateLimitConfig,
    RateLimitStore,
    ScheduleOptions,
    create_memory_store,
)


class RateLimitTransport(httpx.AsyncBaseTransport):
    """
    Rate limiting transport wrapper for httpx.

    Wraps another transport and applies rate limiting to all requests.
    Implements the "Transport Wrapping" pattern for HTTPX composition.

    Example:
        base = httpx.AsyncHTTPTransport()
        transport = RateLimitTransport(base, max_per_second=10)
        client = httpx.AsyncClient(transport=transport)
    """

    def __init__(
        self,
        inner: httpx.AsyncBaseTransport,
        *,
        max_per_second: Optional[float] = None,
        config: Optional[RateLimiterConfig] = None,
        store: Optional[RateLimitStore] = None,
        respect_retry_after: bool = True,
        methods: Optional[list[str]] = None,
    ) -> None:
        """
        Create a new RateLimitTransport.

        Args:
            inner: The wrapped transport to delegate requests to
            max_per_second: Maximum requests per second (simple config)
            config: Custom rate limiter config (alternative to max_per_second)
            store: Custom store for distributed rate limiting
            respect_retry_after: Whether to respect Retry-After headers. Default: True
            methods: HTTP methods to apply rate limiting to. Default: all
        """
        self._inner = inner
        self._respect_retry_after = respect_retry_after
        self._methods = methods

        # Build rate limiter config
        if config:
            limiter_config = config
        elif max_per_second:
            limiter_config = RateLimiterConfig(
                id=f"transport-{id(self)}",
                static=StaticRateLimitConfig(
                    max_requests=int(max_per_second),
                    interval_seconds=1.0,
                ),
            )
        else:
            limiter_config = RateLimiterConfig(
                id=f"transport-{id(self)}",
                static=StaticRateLimitConfig(
                    max_requests=10,
                    interval_seconds=1.0,
                ),
            )

        self._limiter = RateLimiter(limiter_config, store or create_memory_store())
        self._retry_after_until: float = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handle an async HTTP request with rate limiting"""

        # Check if this method should be rate limited
        if self._methods and request.method not in self._methods:
            return await self._inner.handle_async_request(request)

        # Check if we need to wait due to Retry-After
        if self._retry_after_until > time.time():
            wait_time = self._retry_after_until - time.time()
            await asyncio.sleep(wait_time)

        # Schedule the request through the rate limiter
        async def execute_request() -> httpx.Response:
            response = await self._inner.handle_async_request(request)

            # Handle Retry-After header
            if self._respect_retry_after and response.status_code == 429:
                retry_after = response.headers.get("retry-after")
                if retry_after:
                    wait_seconds = self._parse_retry_after(retry_after)
                    if wait_seconds > 0:
                        self._retry_after_until = time.time() + wait_seconds

            return response

        result = await self._limiter.schedule(
            execute_request,
            ScheduleOptions(
                metadata={
                    "method": request.method,
                    "url": str(request.url),
                }
            ),
        )

        return result.result

    def _parse_retry_after(self, value: str) -> float:
        """Parse Retry-After header value"""
        # Try parsing as seconds
        try:
            return float(value)
        except ValueError:
            pass

        # Try parsing as HTTP-date
        try:
            dt = parsedate_to_datetime(value)
            return max(0, (dt.timestamp() - time.time()))
        except (ValueError, TypeError):
            pass

        return 0

    async def aclose(self) -> None:
        """Close the transport"""
        await self._limiter.destroy()
        await self._inner.aclose()


class SyncRateLimitTransport(httpx.BaseTransport):
    """
    Synchronous rate limiting transport wrapper for httpx.

    Note: Uses threading for rate limiting in sync context.
    For async applications, use RateLimitTransport instead.
    """

    def __init__(
        self,
        inner: httpx.BaseTransport,
        *,
        max_per_second: Optional[float] = None,
        respect_retry_after: bool = True,
        methods: Optional[list[str]] = None,
    ) -> None:
        """
        Create a new SyncRateLimitTransport.

        Args:
            inner: The wrapped transport to delegate requests to
            max_per_second: Maximum requests per second
            respect_retry_after: Whether to respect Retry-After headers. Default: True
            methods: HTTP methods to apply rate limiting to. Default: all
        """
        self._inner = inner
        self._max_per_second = max_per_second or 10
        self._respect_retry_after = respect_retry_after
        self._methods = methods

        # Simple token bucket for sync rate limiting
        self._interval = 1.0 / self._max_per_second
        self._last_request: float = 0
        self._retry_after_until: float = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Handle a sync HTTP request with rate limiting"""

        # Check if this method should be rate limited
        if self._methods and request.method not in self._methods:
            return self._inner.handle_request(request)

        # Check if we need to wait due to Retry-After
        if self._retry_after_until > time.time():
            wait_time = self._retry_after_until - time.time()
            time.sleep(wait_time)

        # Apply rate limiting
        now = time.time()
        elapsed = now - self._last_request
        if elapsed < self._interval:
            time.sleep(self._interval - elapsed)

        self._last_request = time.time()

        # Make the request
        response = self._inner.handle_request(request)

        # Handle Retry-After header
        if self._respect_retry_after and response.status_code == 429:
            retry_after = response.headers.get("retry-after")
            if retry_after:
                wait_seconds = self._parse_retry_after(retry_after)
                if wait_seconds > 0:
                    self._retry_after_until = time.time() + wait_seconds

        return response

    def _parse_retry_after(self, value: str) -> float:
        """Parse Retry-After header value"""
        try:
            return float(value)
        except ValueError:
            pass

        try:
            dt = parsedate_to_datetime(value)
            return max(0, (dt.timestamp() - time.time()))
        except (ValueError, TypeError):
            pass

        return 0

    def close(self) -> None:
        """Close the transport"""
        self._inner.close()
