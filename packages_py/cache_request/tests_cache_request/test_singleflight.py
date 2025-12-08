"""
Tests for Singleflight (Request Coalescing).

Coverage includes:
- Statement coverage: All executable statements
- Decision/Branch coverage: All conditional branches
- Condition coverage: Boolean conditions in decisions
- Path coverage: Key execution paths including concurrent paths
- Boundary testing: Edge cases
- State transitions: In-flight request lifecycle
- Error handling: Error propagation to all subscribers
- Event emission: Observer pattern verification
- Concurrency testing: Multiple concurrent requests
"""
import asyncio
import time
import pytest
from typing import List

from cache_request import (
    Singleflight,
    create_singleflight,
    SingleflightConfig,
    RequestFingerprint,
    CacheRequestEvent,
    CacheRequestEventType,
    MemorySingleflightStore,
    DEFAULT_SINGLEFLIGHT_CONFIG,
    merge_singleflight_config,
)


async def async_value(value="value"):
    """Helper to create a simple async function returning a value."""
    return value


class TestSingleflight:
    """Tests for Singleflight."""

    @pytest.fixture
    def singleflight(self) -> Singleflight:
        """Create a fresh singleflight instance for each test."""
        sf = Singleflight()
        yield sf
        sf.close()

    # === Constructor tests ===

    def test_constructor_with_default_config(self) -> None:
        """Should create with default configuration."""
        sf = Singleflight()
        config = sf.get_config()

        assert config.ttl_seconds == 30
        assert config.methods == ["GET", "HEAD"]
        assert config.include_headers is False

        sf.close()

    def test_constructor_with_custom_config(self) -> None:
        """Should create with custom configuration."""
        sf = Singleflight(
            SingleflightConfig(
                ttl_seconds=60,
                methods=["GET", "HEAD", "OPTIONS"],
                include_headers=True,
                header_keys=["Authorization"],
            )
        )

        config = sf.get_config()
        assert config.ttl_seconds == 60
        assert config.methods == ["GET", "HEAD", "OPTIONS"]
        assert config.include_headers is True
        assert config.header_keys == ["Authorization"]

        sf.close()

    def test_constructor_with_custom_store(self) -> None:
        """Should accept custom store."""
        store = MemorySingleflightStore()
        sf = Singleflight(store=store)

        assert sf is not None
        sf.close()

    def test_constructor_with_custom_fingerprint_generator(self) -> None:
        """Should accept custom fingerprint generator."""
        sf = Singleflight(
            SingleflightConfig(
                fingerprint_generator=lambda req: f"custom:{req.method}:{req.url}"
            )
        )

        fingerprint = sf.generate_fingerprint(
            RequestFingerprint(method="GET", url="/api/test")
        )

        assert fingerprint == "custom:GET:/api/test"
        sf.close()

    # === supports_coalescing() tests ===

    def test_supports_coalescing_get(
        self, singleflight: Singleflight
    ) -> None:
        """Should return True for GET."""
        assert singleflight.supports_coalescing("GET") is True

    def test_supports_coalescing_head(
        self, singleflight: Singleflight
    ) -> None:
        """Should return True for HEAD."""
        assert singleflight.supports_coalescing("HEAD") is True

    def test_supports_coalescing_post(
        self, singleflight: Singleflight
    ) -> None:
        """Should return False for POST."""
        assert singleflight.supports_coalescing("POST") is False

    def test_supports_coalescing_put(
        self, singleflight: Singleflight
    ) -> None:
        """Should return False for PUT."""
        assert singleflight.supports_coalescing("PUT") is False

    def test_supports_coalescing_patch(
        self, singleflight: Singleflight
    ) -> None:
        """Should return False for PATCH."""
        assert singleflight.supports_coalescing("PATCH") is False

    def test_supports_coalescing_delete(
        self, singleflight: Singleflight
    ) -> None:
        """Should return False for DELETE."""
        assert singleflight.supports_coalescing("DELETE") is False

    def test_supports_coalescing_case_insensitive(
        self, singleflight: Singleflight
    ) -> None:
        """Should be case-insensitive."""
        assert singleflight.supports_coalescing("get") is True
        assert singleflight.supports_coalescing("Get") is True
        assert singleflight.supports_coalescing("GET") is True

    def test_supports_coalescing_custom_methods(self) -> None:
        """Should respect custom methods configuration."""
        sf = Singleflight(SingleflightConfig(methods=["POST", "PUT"]))

        assert sf.supports_coalescing("GET") is False
        assert sf.supports_coalescing("POST") is True
        assert sf.supports_coalescing("PUT") is True

        sf.close()

    # === generate_fingerprint() tests ===

    def test_generate_fingerprint_consistent(
        self, singleflight: Singleflight
    ) -> None:
        """Should generate consistent fingerprint for same request."""
        request = RequestFingerprint(method="GET", url="/api/test")

        fp1 = singleflight.generate_fingerprint(request)
        fp2 = singleflight.generate_fingerprint(request)

        assert fp1 == fp2

    def test_generate_fingerprint_different_urls(
        self, singleflight: Singleflight
    ) -> None:
        """Should generate different fingerprints for different URLs."""
        fp1 = singleflight.generate_fingerprint(
            RequestFingerprint(method="GET", url="/api/test1")
        )
        fp2 = singleflight.generate_fingerprint(
            RequestFingerprint(method="GET", url="/api/test2")
        )

        assert fp1 != fp2

    def test_generate_fingerprint_different_methods(
        self, singleflight: Singleflight
    ) -> None:
        """Should generate different fingerprints for different methods."""
        fp1 = singleflight.generate_fingerprint(
            RequestFingerprint(method="GET", url="/api/test")
        )
        fp2 = singleflight.generate_fingerprint(
            RequestFingerprint(method="HEAD", url="/api/test")
        )

        assert fp1 != fp2

    def test_generate_fingerprint_includes_body(
        self, singleflight: Singleflight
    ) -> None:
        """Should include body in fingerprint."""
        fp1 = singleflight.generate_fingerprint(
            RequestFingerprint(method="GET", url="/api/test", body=b"body1")
        )
        fp2 = singleflight.generate_fingerprint(
            RequestFingerprint(method="GET", url="/api/test", body=b"body2")
        )

        assert fp1 != fp2

    def test_generate_fingerprint_excludes_headers_by_default(
        self, singleflight: Singleflight
    ) -> None:
        """Should exclude headers by default."""
        fp1 = singleflight.generate_fingerprint(
            RequestFingerprint(
                method="GET", url="/api/test", headers={"X-Custom": "value1"}
            )
        )
        fp2 = singleflight.generate_fingerprint(
            RequestFingerprint(
                method="GET", url="/api/test", headers={"X-Custom": "value2"}
            )
        )

        assert fp1 == fp2

    def test_generate_fingerprint_includes_selected_headers(self) -> None:
        """Should include selected headers when configured."""
        sf = Singleflight(
            SingleflightConfig(include_headers=True, header_keys=["Authorization"])
        )

        fp1 = sf.generate_fingerprint(
            RequestFingerprint(
                method="GET", url="/api/test", headers={"Authorization": "Bearer token1"}
            )
        )
        fp2 = sf.generate_fingerprint(
            RequestFingerprint(
                method="GET", url="/api/test", headers={"Authorization": "Bearer token2"}
            )
        )

        assert fp1 != fp2
        sf.close()

    # === do() tests ===

    async def test_do_executes_and_returns_result(
        self, singleflight: Singleflight
    ) -> None:
        """Should execute function and return result."""
        request = RequestFingerprint(method="GET", url="/api/test")

        result = await singleflight.do(request, lambda: async_value("test-value"))

        assert result.value == "test-value"
        assert result.shared is False
        assert result.subscribers == 1

    async def test_do_coalesces_identical_requests(
        self, singleflight: Singleflight
    ) -> None:
        """Should coalesce identical concurrent requests."""
        request = RequestFingerprint(method="GET", url="/api/test")
        call_count = {"value": 0}

        async def fn() -> str:
            call_count["value"] += 1
            await asyncio.sleep(0.05)
            return "shared-value"

        results = await asyncio.gather(
            singleflight.do(request, fn),
            singleflight.do(request, fn),
            singleflight.do(request, fn),
        )

        assert call_count["value"] == 1
        assert all(r.value == "shared-value" for r in results)

        # One should be the leader, others should be shared
        shared_count = sum(1 for r in results if r.shared)
        assert shared_count == 2

    async def test_do_does_not_coalesce_different_requests(
        self, singleflight: Singleflight
    ) -> None:
        """Should not coalesce different requests."""
        call_count = {"value": 0}

        async def fn() -> str:
            call_count["value"] += 1
            return f"value-{call_count['value']}"

        results = await asyncio.gather(
            singleflight.do(RequestFingerprint(method="GET", url="/api/test1"), fn),
            singleflight.do(RequestFingerprint(method="GET", url="/api/test2"), fn),
        )

        assert call_count["value"] == 2
        assert results[0].value != results[1].value

    async def test_do_propagates_errors_to_all_subscribers(
        self, singleflight: Singleflight
    ) -> None:
        """Should propagate errors to all subscribers."""
        request = RequestFingerprint(method="GET", url="/api/test")
        error = Exception("Test error")

        async def fn() -> str:
            await asyncio.sleep(0.02)
            raise error

        results = await asyncio.gather(
            singleflight.do(request, fn),
            singleflight.do(request, fn),
            singleflight.do(request, fn),
            return_exceptions=True,
        )

        assert all(isinstance(r, Exception) for r in results)

    async def test_do_removes_request_after_completion(
        self, singleflight: Singleflight
    ) -> None:
        """Should remove in-flight request after completion."""
        request = RequestFingerprint(method="GET", url="/api/test")

        await singleflight.do(request, lambda: async_value())

        assert singleflight.is_in_flight(request) is False

    async def test_do_removes_request_after_error(
        self, singleflight: Singleflight
    ) -> None:
        """Should remove in-flight request after error."""
        request = RequestFingerprint(method="GET", url="/api/test")

        async def fn() -> str:
            raise Exception("Test error")

        try:
            await singleflight.do(request, fn)
        except Exception:
            pass

        assert singleflight.is_in_flight(request) is False

    async def test_do_tracks_correct_subscriber_count(
        self, singleflight: Singleflight
    ) -> None:
        """Should track correct subscriber count."""
        request = RequestFingerprint(method="GET", url="/api/test")
        resolve_event = asyncio.Event()

        async def fn() -> str:
            await resolve_event.wait()
            return "value"

        # Start requests
        tasks = [
            asyncio.create_task(singleflight.do(request, fn)),
            asyncio.create_task(singleflight.do(request, fn)),
            asyncio.create_task(singleflight.do(request, fn)),
        ]

        # Wait for all to register
        await asyncio.sleep(0.01)

        assert singleflight.get_subscribers(request) == 3

        resolve_event.set()
        results = await asyncio.gather(*tasks)

        assert all(r.subscribers == 3 for r in results)

    async def test_do_emits_lead_event(
        self, singleflight: Singleflight
    ) -> None:
        """Should emit singleflight:lead event for leader."""
        events: List[CacheRequestEvent] = []
        singleflight.on(lambda e: events.append(e))

        request = RequestFingerprint(method="GET", url="/api/test")
        await singleflight.do(request, lambda: async_value())

        lead_events = [e for e in events if e.type == CacheRequestEventType.SINGLEFLIGHT_LEAD]
        assert len(lead_events) == 1

    async def test_do_emits_join_event_for_followers(
        self, singleflight: Singleflight
    ) -> None:
        """Should emit singleflight:join event for followers."""
        events: List[CacheRequestEvent] = []
        singleflight.on(lambda e: events.append(e))

        request = RequestFingerprint(method="GET", url="/api/test")

        async def fn() -> str:
            await asyncio.sleep(0.02)
            return "value"

        await asyncio.gather(
            singleflight.do(request, fn),
            singleflight.do(request, fn),
            singleflight.do(request, fn),
        )

        join_events = [e for e in events if e.type == CacheRequestEventType.SINGLEFLIGHT_JOIN]
        assert len(join_events) == 2

    async def test_do_emits_complete_event(
        self, singleflight: Singleflight
    ) -> None:
        """Should emit singleflight:complete event on success."""
        events: List[CacheRequestEvent] = []
        singleflight.on(lambda e: events.append(e))

        request = RequestFingerprint(method="GET", url="/api/test")
        await singleflight.do(request, lambda: async_value())

        complete_events = [
            e for e in events if e.type == CacheRequestEventType.SINGLEFLIGHT_COMPLETE
        ]
        assert len(complete_events) == 1
        assert complete_events[0].metadata is not None
        assert "subscribers" in complete_events[0].metadata
        assert "duration_seconds" in complete_events[0].metadata

    async def test_do_emits_error_event_on_failure(
        self, singleflight: Singleflight
    ) -> None:
        """Should emit singleflight:error event on failure."""
        events: List[CacheRequestEvent] = []
        singleflight.on(lambda e: events.append(e))

        request = RequestFingerprint(method="GET", url="/api/test")

        async def fn() -> str:
            raise Exception("Test error")

        try:
            await singleflight.do(request, fn)
        except Exception:
            pass

        error_events = [
            e for e in events if e.type == CacheRequestEventType.SINGLEFLIGHT_ERROR
        ]
        assert len(error_events) == 1
        assert error_events[0].metadata is not None
        assert "error" in error_events[0].metadata

    # === is_in_flight() tests ===

    async def test_is_in_flight_false_for_nonexistent(
        self, singleflight: Singleflight
    ) -> None:
        """Should return False for non-existent request."""
        request = RequestFingerprint(method="GET", url="/api/test")
        assert singleflight.is_in_flight(request) is False

    async def test_is_in_flight_true_for_in_flight(
        self, singleflight: Singleflight
    ) -> None:
        """Should return True for in-flight request."""
        request = RequestFingerprint(method="GET", url="/api/test")
        resolve_event = asyncio.Event()

        async def fn() -> str:
            await resolve_event.wait()
            return "value"

        task = asyncio.create_task(singleflight.do(request, fn))

        await asyncio.sleep(0.01)
        assert singleflight.is_in_flight(request) is True

        resolve_event.set()
        await task

        assert singleflight.is_in_flight(request) is False

    # === get_subscribers() tests ===

    def test_get_subscribers_zero_for_nonexistent(
        self, singleflight: Singleflight
    ) -> None:
        """Should return 0 for non-existent request."""
        request = RequestFingerprint(method="GET", url="/api/test")
        assert singleflight.get_subscribers(request) == 0

    async def test_get_subscribers_correct_count(
        self, singleflight: Singleflight
    ) -> None:
        """Should return correct subscriber count."""
        request = RequestFingerprint(method="GET", url="/api/test")
        resolve_event = asyncio.Event()

        async def fn() -> str:
            await resolve_event.wait()
            return "value"

        tasks = [
            asyncio.create_task(singleflight.do(request, fn)),
            asyncio.create_task(singleflight.do(request, fn)),
        ]

        await asyncio.sleep(0.01)
        assert singleflight.get_subscribers(request) == 2

        resolve_event.set()
        await asyncio.gather(*tasks)

    # === get_stats() tests ===

    async def test_get_stats_in_flight_count(
        self, singleflight: Singleflight
    ) -> None:
        """Should return correct in-flight count."""
        assert singleflight.get_stats()["in_flight"] == 0

        resolve_events = [asyncio.Event(), asyncio.Event()]

        async def fn1() -> str:
            await resolve_events[0].wait()
            return "value1"

        async def fn2() -> str:
            await resolve_events[1].wait()
            return "value2"

        task1 = asyncio.create_task(
            singleflight.do(RequestFingerprint(method="GET", url="/api/test1"), fn1)
        )
        task2 = asyncio.create_task(
            singleflight.do(RequestFingerprint(method="GET", url="/api/test2"), fn2)
        )

        await asyncio.sleep(0.01)
        assert singleflight.get_stats()["in_flight"] == 2

        resolve_events[0].set()
        await task1
        assert singleflight.get_stats()["in_flight"] == 1

        resolve_events[1].set()
        await task2
        assert singleflight.get_stats()["in_flight"] == 0

    # === Event listeners tests ===

    async def test_on_adds_listener(
        self, singleflight: Singleflight
    ) -> None:
        """Should add listener with on()."""
        events: List[CacheRequestEvent] = []
        singleflight.on(lambda e: events.append(e))

        await singleflight.do(
            RequestFingerprint(method="GET", url="/api/test"),
            lambda: async_value(),
        )

        assert len(events) > 0

    async def test_on_returns_unsubscribe(
        self, singleflight: Singleflight
    ) -> None:
        """Should return unsubscribe function from on()."""
        events: List[CacheRequestEvent] = []
        unsubscribe = singleflight.on(lambda e: events.append(e))

        await singleflight.do(
            RequestFingerprint(method="GET", url="/api/test1"),
            lambda: async_value(),
        )

        count_after_first = len(events)

        unsubscribe()

        await singleflight.do(
            RequestFingerprint(method="GET", url="/api/test2"),
            lambda: async_value(),
        )

        assert len(events) == count_after_first

    async def test_off_removes_listener(
        self, singleflight: Singleflight
    ) -> None:
        """Should remove listener with off()."""
        events: List[CacheRequestEvent] = []
        listener = lambda e: events.append(e)

        singleflight.on(listener)
        await singleflight.do(
            RequestFingerprint(method="GET", url="/api/test1"),
            lambda: async_value(),
        )

        count_after_first = len(events)

        singleflight.off(listener)
        await singleflight.do(
            RequestFingerprint(method="GET", url="/api/test2"),
            lambda: async_value(),
        )

        assert len(events) == count_after_first

    async def test_listener_errors_handled_gracefully(
        self, singleflight: Singleflight
    ) -> None:
        """Should handle listener errors gracefully."""

        def error_listener(event: CacheRequestEvent) -> None:
            raise Exception("Listener error")

        singleflight.on(error_listener)

        # Should not throw
        await singleflight.do(
            RequestFingerprint(method="GET", url="/api/test"),
            lambda: async_value(),
        )

    # === clear() tests ===

    async def test_clear_removes_all_requests(
        self, singleflight: Singleflight
    ) -> None:
        """Should clear all in-flight requests."""
        resolve_event = asyncio.Event()

        async def fn() -> str:
            await resolve_event.wait()
            return "value"

        task = asyncio.create_task(
            singleflight.do(RequestFingerprint(method="GET", url="/api/test"), fn)
        )

        await asyncio.sleep(0.01)
        assert singleflight.get_stats()["in_flight"] == 1

        singleflight.clear()
        assert singleflight.get_stats()["in_flight"] == 0

        resolve_event.set()
        # Task may fail or succeed depending on timing, just wait for it
        try:
            await task
        except Exception:
            pass

    # === close() tests ===

    async def test_close_clears_requests(
        self, singleflight: Singleflight
    ) -> None:
        """Should clear in-flight requests."""
        resolve_event = asyncio.Event()

        async def fn() -> str:
            await resolve_event.wait()
            return "value"

        task = asyncio.create_task(
            singleflight.do(RequestFingerprint(method="GET", url="/api/test"), fn)
        )

        await asyncio.sleep(0.01)

        singleflight.close()
        assert singleflight.get_stats()["in_flight"] == 0

        resolve_event.set()
        try:
            await task
        except Exception:
            pass

    # === Boundary conditions ===

    async def test_boundary_empty_url(
        self, singleflight: Singleflight
    ) -> None:
        """Should handle empty URL."""
        result = await singleflight.do(
            RequestFingerprint(method="GET", url=""),
            lambda: async_value(),
        )
        assert result.value == "value"

    async def test_boundary_very_long_url(
        self, singleflight: Singleflight
    ) -> None:
        """Should handle very long URL."""
        long_url = "/api/" + "a" * 10000
        result = await singleflight.do(
            RequestFingerprint(method="GET", url=long_url),
            lambda: async_value(),
        )
        assert result.value == "value"

    async def test_boundary_special_chars_in_url(
        self, singleflight: Singleflight
    ) -> None:
        """Should handle special characters in URL."""
        result = await singleflight.do(
            RequestFingerprint(method="GET", url="/api/test?query=a&b=c#hash"),
            lambda: async_value(),
        )
        assert result.value == "value"

    async def test_boundary_complex_return_types(
        self, singleflight: Singleflight
    ) -> None:
        """Should handle complex return types."""

        async def fn() -> dict:
            return {"nested": {"data": [1, 2, 3]}}

        result = await singleflight.do(
            RequestFingerprint(method="GET", url="/api/test"), fn
        )
        assert result.value == {"nested": {"data": [1, 2, 3]}}

    # === Concurrent operations ===

    async def test_concurrent_many_coalesced_requests(
        self, singleflight: Singleflight
    ) -> None:
        """Should handle many concurrent coalesced requests."""
        request = RequestFingerprint(method="GET", url="/api/test")
        call_count = {"value": 0}

        async def fn() -> str:
            call_count["value"] += 1
            await asyncio.sleep(0.02)
            return "shared"

        results = await asyncio.gather(
            *[singleflight.do(request, fn) for _ in range(50)]
        )

        assert call_count["value"] == 1
        assert all(r.value == "shared" for r in results)
        assert sum(1 for r in results if r.shared) == 49

    async def test_concurrent_many_different_requests(
        self, singleflight: Singleflight
    ) -> None:
        """Should handle many different concurrent requests."""
        call_count = {"value": 0}

        async def fn() -> str:
            call_count["value"] += 1
            return f"value{call_count['value']}"

        results = await asyncio.gather(
            *[
                singleflight.do(RequestFingerprint(method="GET", url=f"/api/test{i}"), fn)
                for i in range(50)
            ]
        )

        assert call_count["value"] == 50
        assert all(not r.shared for r in results)

    # === State transitions ===

    async def test_state_idle_to_in_flight_to_completed(
        self, singleflight: Singleflight
    ) -> None:
        """Should transition: idle -> in-flight -> completed -> idle."""
        request = RequestFingerprint(method="GET", url="/api/test")
        resolve_event = asyncio.Event()

        async def fn() -> str:
            await resolve_event.wait()
            return "value"

        # Idle state
        assert singleflight.is_in_flight(request) is False

        # In-flight state
        task = asyncio.create_task(singleflight.do(request, fn))
        await asyncio.sleep(0.01)
        assert singleflight.is_in_flight(request) is True

        # Completed -> Idle
        resolve_event.set()
        await task
        assert singleflight.is_in_flight(request) is False

    async def test_state_idle_to_in_flight_to_error_to_idle(
        self, singleflight: Singleflight
    ) -> None:
        """Should transition: idle -> in-flight -> error -> idle."""
        request = RequestFingerprint(method="GET", url="/api/test")

        # Idle state
        assert singleflight.is_in_flight(request) is False

        # In-flight -> Error -> Idle
        async def fn() -> str:
            raise Exception("Test")

        try:
            await singleflight.do(request, fn)
        except Exception:
            pass

        assert singleflight.is_in_flight(request) is False


class TestConfigurationHelpers:
    """Tests for configuration helper functions."""

    def test_default_config_values(self) -> None:
        """Should have correct default values."""
        assert DEFAULT_SINGLEFLIGHT_CONFIG.ttl_seconds == 30
        assert DEFAULT_SINGLEFLIGHT_CONFIG.methods == ["GET", "HEAD"]
        assert DEFAULT_SINGLEFLIGHT_CONFIG.include_headers is False
        assert DEFAULT_SINGLEFLIGHT_CONFIG.header_keys == []
        assert callable(DEFAULT_SINGLEFLIGHT_CONFIG.fingerprint_generator)

    def test_merge_config_with_none(self) -> None:
        """Should return defaults when no config provided."""
        merged = merge_singleflight_config(None)
        assert merged.ttl_seconds == 30
        assert merged.methods == ["GET", "HEAD"]

    def test_merge_config_with_partial(self) -> None:
        """Should merge partial config with defaults."""
        merged = merge_singleflight_config(SingleflightConfig(ttl_seconds=60))
        assert merged.ttl_seconds == 60
        assert merged.methods == ["GET", "HEAD"]

    def test_merge_config_preserves_custom(self) -> None:
        """Should preserve all custom values."""
        custom = SingleflightConfig(
            ttl_seconds=10,
            methods=["OPTIONS"],
            include_headers=True,
            header_keys=["X-Custom"],
        )
        merged = merge_singleflight_config(custom)

        assert merged.ttl_seconds == 10
        assert merged.methods == ["OPTIONS"]
        assert merged.include_headers is True
        assert merged.header_keys == ["X-Custom"]


class TestFactoryFunction:
    """Tests for create_singleflight factory."""

    def test_creates_singleflight_with_default_config(self) -> None:
        """Should create singleflight with default config."""
        sf = create_singleflight()
        assert isinstance(sf, Singleflight)
        sf.close()

    def test_creates_singleflight_with_custom_config(self) -> None:
        """Should create singleflight with custom config."""
        sf = create_singleflight(SingleflightConfig(ttl_seconds=1000))
        assert sf.get_config().ttl_seconds == 1000
        sf.close()

    def test_creates_singleflight_with_custom_store(self) -> None:
        """Should create singleflight with custom store."""
        store = MemorySingleflightStore()
        sf = create_singleflight(store=store)
        assert isinstance(sf, Singleflight)
        sf.close()
