"""
Main rate limiter implementation
"""
import asyncio
import time
from typing import TypeVar, Callable, Awaitable, Optional, Any
from .types import (
    RateLimiterConfig,
    RateLimiterStats,
    RateLimiterEvent,
    RateLimiterEventListener,
    ScheduleOptions,
    ScheduleResult,
    QueuedRequest,
    RateLimitStore,
    StaticRateLimitConfig,
)
from .config import (
    merge_config,
    calculate_backoff_delay,
    is_retryable_error,
    generate_request_id,
    async_sleep,
    DEFAULT_RETRY_CONFIG,
)
from .queue import PriorityQueue
from .stores.memory import MemoryStore


T = TypeVar("T")


class RateLimiter:
    """
    API Rate Limiter

    Manages outgoing API requests with:
    - Static or dynamic rate limiting
    - Priority queue with FIFO ordering within priorities
    - Retry with exponential backoff and jitter
    - Concurrency control
    - Distributed state via pluggable stores
    """

    def __init__(
        self,
        config: RateLimiterConfig,
        store: Optional[RateLimitStore] = None,
    ) -> None:
        """
        Create a new RateLimiter.

        Args:
            config: Rate limiter configuration
            store: Optional custom store for distributed rate limiting
        """
        self._config = merge_config(config)
        self._queue: PriorityQueue[Any] = PriorityQueue()
        self._store = store or MemoryStore()
        self._listeners: set[RateLimiterEventListener] = set()

        self._active_requests = 0
        self._total_processed = 0
        self._total_rejected = 0
        self._total_queue_time = 0.0
        self._total_execution_time = 0.0
        self._processing = False
        self._destroyed = False
        self._pending_futures: dict[str, asyncio.Future[ScheduleResult[Any]]] = {}

    def _get_store_key(self) -> str:
        """Get the store key for this limiter"""
        return f"limiter:{self._config.id}"

    def _emit(self, event: RateLimiterEvent) -> None:
        """Emit an event to all listeners"""
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass

    async def _can_make_request(self) -> tuple[bool, float]:
        """Check if we can make a request based on rate limits"""
        if self._config.dynamic:
            try:
                status = await self._config.dynamic.get_rate_limit_status()
                if status.remaining <= 0:
                    wait = max(0, status.reset - time.time())
                    return False, wait
                return True, 0
            except Exception:
                if self._config.dynamic.fallback:
                    return await self._check_static_limit(self._config.dynamic.fallback)
                return True, 0

        if self._config.static:
            return await self._check_static_limit(self._config.static)

        return True, 0

    async def _check_static_limit(
        self, config: StaticRateLimitConfig
    ) -> tuple[bool, float]:
        """Check static rate limit"""
        key = self._get_store_key()
        count = await self._store.get_count(key)

        if count >= config.max_requests:
            ttl = await self._store.get_ttl(key)
            return False, ttl

        return True, 0

    async def _record_request(self) -> None:
        """Record a request for rate limiting"""
        if self._config.static:
            key = self._get_store_key()
            await self._store.increment(key, self._config.static.interval_seconds)

    async def _process_queue(self) -> None:
        """Process the queue"""
        if self._processing or self._destroyed:
            return

        self._processing = True

        try:
            while not self._queue.is_empty() and not self._destroyed:
                # Check concurrency limit
                if self._active_requests >= self._config.concurrency:
                    break

                # Remove expired requests
                now = time.time()
                expired = self._queue.remove_expired(now)
                for req in expired:
                    self._emit(
                        RateLimiterEvent(
                            type="request:expired",
                            data={"deadline": req.deadline, "metadata": req.metadata},
                        )
                    )
                    future = self._pending_futures.pop(req.id, None)
                    if future and not future.done():
                        future.set_exception(Exception("Request deadline exceeded"))
                    self._total_rejected += 1

                # Check rate limit
                allowed, wait = await self._can_make_request()
                if not allowed:
                    self._emit(
                        RateLimiterEvent(type="rate:limited", data={"wait_seconds": wait})
                    )
                    await async_sleep(wait)
                    continue

                # Get next request
                request = self._queue.dequeue()
                if not request:
                    break

                # Process request concurrently
                asyncio.create_task(self._execute_request(request))

        finally:
            self._processing = False

    async def _execute_request(self, request: QueuedRequest[Any]) -> None:
        """Execute a single request with retries"""
        queue_time = time.time() - request.enqueued_at
        self._total_queue_time += queue_time
        self._active_requests += 1

        self._emit(
            RateLimiterEvent(
                type="request:started",
                data={"metadata": request.metadata},
            )
        )

        start_time = time.time()
        retries = 0
        last_error: Optional[Exception] = None
        retry_config = self._config.retry or DEFAULT_RETRY_CONFIG

        try:
            await self._record_request()

            max_retries = retry_config.max_retries

            while retries <= max_retries:
                try:
                    result = await request.fn()
                    execution_time = time.time() - start_time
                    self._total_execution_time += execution_time
                    self._total_processed += 1

                    self._emit(
                        RateLimiterEvent(
                            type="request:completed",
                            data={
                                "duration_seconds": execution_time,
                                "metadata": request.metadata,
                            },
                        )
                    )

                    schedule_result = ScheduleResult(
                        result=result,
                        queue_time=queue_time,
                        execution_time=execution_time,
                        retries=retries,
                    )

                    future = self._pending_futures.pop(request.id, None)
                    if future and not future.done():
                        future.set_result(schedule_result)

                    return

                except Exception as error:
                    last_error = error

                    if not is_retryable_error(error, retry_config):
                        raise

                    if retries >= max_retries:
                        raise

                    retries += 1
                    delay = calculate_backoff_delay(retries, retry_config)

                    self._emit(
                        RateLimiterEvent(
                            type="request:requeued",
                            data={
                                "reason": str(error),
                                "metadata": request.metadata,
                            },
                        )
                    )

                    await async_sleep(delay)

            if last_error:
                raise last_error

        except Exception as error:
            self._emit(
                RateLimiterEvent(
                    type="request:failed",
                    data={
                        "error": str(error),
                        "retries": retries,
                        "metadata": request.metadata,
                    },
                )
            )

            future = self._pending_futures.pop(request.id, None)
            if future and not future.done():
                future.set_exception(error)

            self._total_rejected += 1

        finally:
            self._active_requests -= 1
            # Trigger queue processing
            asyncio.get_event_loop().call_soon(
                lambda: asyncio.create_task(self._process_queue())
            )

    async def schedule(
        self,
        fn: Callable[[], Awaitable[T]],
        options: Optional[ScheduleOptions] = None,
    ) -> ScheduleResult[T]:
        """
        Schedule a function for rate-limited execution.

        Args:
            fn: Async function to execute
            options: Schedule options

        Returns:
            Promise resolving to the schedule result

        Example:
            result = await limiter.schedule(
                lambda: httpx_client.get('https://api.example.com/data'),
                ScheduleOptions(priority=1)
            )
        """
        if self._destroyed:
            raise Exception("RateLimiter has been destroyed")

        opts = options or ScheduleOptions()
        max_queue_size = self._config.max_queue_size

        if max_queue_size is not None and self._queue.size >= max_queue_size:
            self._total_rejected += 1
            raise Exception("Queue is full")

        request_id = generate_request_id()
        request: QueuedRequest[T] = QueuedRequest(
            id=request_id,
            fn=fn,
            priority=opts.priority,
            enqueued_at=time.time(),
            deadline=opts.deadline,
            metadata=opts.metadata,
        )

        future: asyncio.Future[ScheduleResult[T]] = asyncio.get_event_loop().create_future()
        self._pending_futures[request_id] = future

        self._queue.enqueue(request)

        self._emit(
            RateLimiterEvent(
                type="request:queued",
                data={"priority": opts.priority, "queue_size": self._queue.size},
            )
        )

        # Trigger queue processing
        asyncio.create_task(self._process_queue())

        return await future

    def get_stats(self) -> RateLimiterStats:
        """Get current statistics"""
        processed = max(1, self._total_processed)  # Avoid division by zero
        return RateLimiterStats(
            queue_size=self._queue.size,
            active_requests=self._active_requests,
            total_processed=self._total_processed,
            total_rejected=self._total_rejected,
            avg_queue_time_seconds=self._total_queue_time / processed,
            avg_execution_time_seconds=self._total_execution_time / processed,
        )

    def on(self, listener: RateLimiterEventListener) -> Callable[[], None]:
        """
        Add an event listener.

        Args:
            listener: Event listener function

        Returns:
            Function to remove the listener
        """
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def off(self, listener: RateLimiterEventListener) -> None:
        """Remove an event listener"""
        self._listeners.discard(listener)

    async def destroy(self) -> None:
        """Destroy the rate limiter and clean up resources"""
        self._destroyed = True

        # Reject all pending requests
        pending = self._queue.clear()
        for request in pending:
            future = self._pending_futures.pop(request.id, None)
            if future and not future.done():
                future.set_exception(Exception("RateLimiter destroyed"))

        # Close the store
        await self._store.close()

        # Clear listeners
        self._listeners.clear()


def create_rate_limiter(
    config: RateLimiterConfig,
    store: Optional[RateLimitStore] = None,
) -> RateLimiter:
    """Create a new rate limiter instance"""
    return RateLimiter(config, store)
