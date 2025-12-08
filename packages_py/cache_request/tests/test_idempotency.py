"""
Tests for IdempotencyManager.

Coverage includes:
- Statement coverage: All executable statements
- Decision/Branch coverage: All conditional branches
- Condition coverage: Boolean conditions in decisions
- Path coverage: Key execution paths
- Boundary testing: TTL limits, key validation
- State transitions: Lifecycle of idempotency entries
- Error handling: Conflict detection, validation errors
- Event emission: Observer pattern verification
"""
import asyncio
import time
import pytest
from typing import List
from unittest.mock import MagicMock

from cache_request import (
    IdempotencyManager,
    IdempotencyConflictError,
    create_idempotency_manager,
    IdempotencyConfig,
    RequestFingerprint,
    CacheRequestEvent,
    CacheRequestEventType,
    MemoryCacheStore,
    DEFAULT_IDEMPOTENCY_CONFIG,
    merge_idempotency_config,
    generate_fingerprint,
)


class TestIdempotencyManager:
    """Tests for IdempotencyManager."""

    @pytest.fixture
    async def manager(self) -> IdempotencyManager:
        """Create a fresh manager for each test."""
        mgr = IdempotencyManager()
        yield mgr
        await mgr.close()

    # === Constructor tests ===

    async def test_constructor_with_default_config(self) -> None:
        """Should create with default configuration."""
        manager = IdempotencyManager()
        config = manager.get_config()

        assert config.header_name == "Idempotency-Key"
        assert config.ttl_seconds == 86400
        assert config.auto_generate is True
        assert config.methods == ["POST", "PATCH"]

        await manager.close()

    async def test_constructor_with_custom_config(self) -> None:
        """Should create with custom configuration."""
        manager = IdempotencyManager(
            IdempotencyConfig(
                header_name="X-Request-Id",
                ttl_seconds=3600,
                auto_generate=False,
                methods=["POST", "PUT"],
            )
        )

        config = manager.get_config()
        assert config.header_name == "X-Request-Id"
        assert config.ttl_seconds == 3600
        assert config.auto_generate is False
        assert config.methods == ["POST", "PUT"]

        await manager.close()

    async def test_constructor_with_custom_store(self) -> None:
        """Should accept custom store."""
        custom_store = MemoryCacheStore()
        manager = IdempotencyManager(store=custom_store)

        key = manager.generate_key()
        await manager.store(key, "test-value")

        check = await manager.check(key)
        assert check.cached is True

        await manager.close()

    async def test_constructor_with_custom_key_generator(self) -> None:
        """Should accept custom key generator."""
        counter = {"value": 0}

        def custom_generator() -> str:
            counter["value"] += 1
            return f"custom-key-{counter['value']}"

        manager = IdempotencyManager(
            IdempotencyConfig(key_generator=custom_generator)
        )

        assert manager.generate_key() == "custom-key-1"
        assert manager.generate_key() == "custom-key-2"

        await manager.close()

    # === generate_key() tests ===

    async def test_generate_key_returns_uuid(
        self, manager: IdempotencyManager
    ) -> None:
        """Should generate a UUID by default."""
        key = manager.generate_key()
        # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        assert len(key) == 36
        assert key.count("-") == 4

    async def test_generate_key_returns_unique_keys(
        self, manager: IdempotencyManager
    ) -> None:
        """Should generate unique keys."""
        keys = set()
        for _ in range(1000):
            keys.add(manager.generate_key())
        assert len(keys) == 1000

    # === requires_idempotency() tests ===

    async def test_requires_idempotency_post(
        self, manager: IdempotencyManager
    ) -> None:
        """Should return True for POST."""
        assert manager.requires_idempotency("POST") is True

    async def test_requires_idempotency_patch(
        self, manager: IdempotencyManager
    ) -> None:
        """Should return True for PATCH."""
        assert manager.requires_idempotency("PATCH") is True

    async def test_requires_idempotency_get(
        self, manager: IdempotencyManager
    ) -> None:
        """Should return False for GET."""
        assert manager.requires_idempotency("GET") is False

    async def test_requires_idempotency_put(
        self, manager: IdempotencyManager
    ) -> None:
        """Should return False for PUT."""
        assert manager.requires_idempotency("PUT") is False

    async def test_requires_idempotency_delete(
        self, manager: IdempotencyManager
    ) -> None:
        """Should return False for DELETE."""
        assert manager.requires_idempotency("DELETE") is False

    async def test_requires_idempotency_case_insensitive(
        self, manager: IdempotencyManager
    ) -> None:
        """Should be case-insensitive."""
        assert manager.requires_idempotency("post") is True
        assert manager.requires_idempotency("Post") is True
        assert manager.requires_idempotency("POST") is True

    async def test_requires_idempotency_custom_methods(self) -> None:
        """Should respect custom methods configuration."""
        manager = IdempotencyManager(
            IdempotencyConfig(methods=["PUT", "DELETE"])
        )

        assert manager.requires_idempotency("POST") is False
        assert manager.requires_idempotency("PUT") is True
        assert manager.requires_idempotency("DELETE") is True

        await manager.close()

    # === check() tests ===

    async def test_check_returns_not_cached_for_new_key(
        self, manager: IdempotencyManager
    ) -> None:
        """Should return cached: False for new key."""
        result = await manager.check("new-key")
        assert result.cached is False
        assert result.key == "new-key"
        assert result.response is None

    async def test_check_returns_cached_for_stored_key(
        self, manager: IdempotencyManager
    ) -> None:
        """Should return cached: True for stored key."""
        key = "stored-key"
        await manager.store(key, {"data": "test"})

        result = await manager.check(key)
        assert result.cached is True
        assert result.key == key
        assert result.response is not None
        assert result.response.value == {"data": "test"}

    async def test_check_returns_not_cached_for_expired_key(self) -> None:
        """Should return cached: False for expired key."""
        manager = IdempotencyManager(IdempotencyConfig(ttl_seconds=0.001))
        key = "expiring-key"
        await manager.store(key, "value")

        await asyncio.sleep(0.002)

        result = await manager.check(key)
        assert result.cached is False

        await manager.close()

    async def test_check_validates_fingerprint(
        self, manager: IdempotencyManager
    ) -> None:
        """Should validate fingerprint if provided."""
        key = "fingerprint-key"
        fingerprint = RequestFingerprint(
            method="POST",
            url="/api/users",
            body=b'{"name":"test"}',
        )

        await manager.store(key, "value", fingerprint)

        # Same fingerprint should work
        result = await manager.check(key, fingerprint)
        assert result.cached is True

    async def test_check_throws_conflict_for_different_fingerprint(
        self, manager: IdempotencyManager
    ) -> None:
        """Should throw IdempotencyConflictError for different fingerprint."""
        key = "conflict-key"
        fingerprint1 = RequestFingerprint(
            method="POST",
            url="/api/users",
            body=b'{"name":"user1"}',
        )
        fingerprint2 = RequestFingerprint(
            method="POST",
            url="/api/users",
            body=b'{"name":"user2"}',
        )

        await manager.store(key, "value", fingerprint1)

        with pytest.raises(IdempotencyConflictError):
            await manager.check(key, fingerprint2)

    async def test_check_emits_hit_event(
        self, manager: IdempotencyManager
    ) -> None:
        """Should emit idempotency:hit event on cache hit."""
        events: List[CacheRequestEvent] = []
        manager.on(lambda e: events.append(e))

        key = "hit-key"
        await manager.store(key, "value")
        await manager.check(key)

        hit_events = [e for e in events if e.type == CacheRequestEventType.IDEMPOTENCY_HIT]
        assert len(hit_events) == 1
        assert hit_events[0].key == key

    async def test_check_emits_miss_event(
        self, manager: IdempotencyManager
    ) -> None:
        """Should emit idempotency:miss event on cache miss."""
        events: List[CacheRequestEvent] = []
        manager.on(lambda e: events.append(e))

        await manager.check("miss-key")

        miss_events = [e for e in events if e.type == CacheRequestEventType.IDEMPOTENCY_MISS]
        assert len(miss_events) == 1
        assert miss_events[0].key == "miss-key"

    # === store() tests ===

    async def test_store_stores_value(
        self, manager: IdempotencyManager
    ) -> None:
        """Should store a value."""
        key = "store-key"
        await manager.store(key, {"data": "stored"})

        check = await manager.check(key)
        assert check.cached is True
        assert check.response is not None
        assert check.response.value == {"data": "stored"}

    async def test_store_with_fingerprint(
        self, manager: IdempotencyManager
    ) -> None:
        """Should store with fingerprint."""
        key = "fingerprint-store-key"
        fingerprint = RequestFingerprint(
            method="POST",
            url="/api/users",
        )

        await manager.store(key, "value", fingerprint)

        check = await manager.check(key, fingerprint)
        assert check.cached is True

    async def test_store_sets_correct_expiration(self) -> None:
        """Should set correct expiration time."""
        manager = IdempotencyManager(IdempotencyConfig(ttl_seconds=0.1))
        key = "expiration-key"

        await manager.store(key, "value")

        # Before expiration
        check = await manager.check(key)
        assert check.cached is True

        # After expiration
        await asyncio.sleep(0.15)
        check = await manager.check(key)
        assert check.cached is False

        await manager.close()

    async def test_store_emits_store_event(
        self, manager: IdempotencyManager
    ) -> None:
        """Should emit idempotency:store event."""
        events: List[CacheRequestEvent] = []
        manager.on(lambda e: events.append(e))

        await manager.store("store-event-key", "value")

        store_events = [e for e in events if e.type == CacheRequestEventType.IDEMPOTENCY_STORE]
        assert len(store_events) == 1
        assert store_events[0].key == "store-event-key"
        assert store_events[0].metadata is not None
        assert "expires_at" in store_events[0].metadata

    async def test_store_overwrites_existing(
        self, manager: IdempotencyManager
    ) -> None:
        """Should overwrite existing entry."""
        key = "overwrite-key"
        await manager.store(key, "first")
        await manager.store(key, "second")

        check = await manager.check(key)
        assert check.response is not None
        assert check.response.value == "second"

    # === invalidate() tests ===

    async def test_invalidate_returns_true_for_existing(
        self, manager: IdempotencyManager
    ) -> None:
        """Should return True when invalidating existing key."""
        key = "invalidate-key"
        await manager.store(key, "value")

        result = await manager.invalidate(key)
        assert result is True

    async def test_invalidate_returns_false_for_nonexistent(
        self, manager: IdempotencyManager
    ) -> None:
        """Should return False when invalidating non-existent key."""
        result = await manager.invalidate("nonexistent")
        assert result is False

    async def test_invalidate_removes_entry(
        self, manager: IdempotencyManager
    ) -> None:
        """Should remove the cached entry."""
        key = "remove-key"
        await manager.store(key, "value")
        await manager.invalidate(key)

        check = await manager.check(key)
        assert check.cached is False

    async def test_invalidate_emits_expire_event(
        self, manager: IdempotencyManager
    ) -> None:
        """Should emit idempotency:expire event."""
        events: List[CacheRequestEvent] = []
        manager.on(lambda e: events.append(e))

        key = "expire-event-key"
        await manager.store(key, "value")
        await manager.invalidate(key)

        expire_events = [e for e in events if e.type == CacheRequestEventType.IDEMPOTENCY_EXPIRE]
        assert len(expire_events) == 1
        assert expire_events[0].key == key

    # === get_header_name() tests ===

    async def test_get_header_name_returns_default(
        self, manager: IdempotencyManager
    ) -> None:
        """Should return default header name."""
        assert manager.get_header_name() == "Idempotency-Key"

    async def test_get_header_name_returns_custom(self) -> None:
        """Should return custom header name."""
        manager = IdempotencyManager(
            IdempotencyConfig(header_name="X-Custom-Idempotency")
        )

        assert manager.get_header_name() == "X-Custom-Idempotency"

        await manager.close()

    # === get_stats() tests ===

    async def test_get_stats_returns_correct_size(
        self, manager: IdempotencyManager
    ) -> None:
        """Should return correct size."""
        stats = await manager.get_stats()
        assert stats["size"] == 0

        await manager.store("key1", "value1")
        stats = await manager.get_stats()
        assert stats["size"] == 1

        await manager.store("key2", "value2")
        stats = await manager.get_stats()
        assert stats["size"] == 2

    # === Event listeners tests ===

    async def test_on_adds_listener(
        self, manager: IdempotencyManager
    ) -> None:
        """Should add listener with on()."""
        events: List[CacheRequestEvent] = []
        manager.on(lambda e: events.append(e))

        await manager.store("key", "value")

        assert len(events) > 0

    async def test_on_returns_unsubscribe(
        self, manager: IdempotencyManager
    ) -> None:
        """Should return unsubscribe function from on()."""
        events: List[CacheRequestEvent] = []
        unsubscribe = manager.on(lambda e: events.append(e))

        await manager.store("key1", "value1")
        store_events_before = len([e for e in events if e.type == CacheRequestEventType.IDEMPOTENCY_STORE])

        unsubscribe()
        await manager.store("key2", "value2")

        store_events_after = len([e for e in events if e.type == CacheRequestEventType.IDEMPOTENCY_STORE])
        assert store_events_after == store_events_before

    async def test_off_removes_listener(
        self, manager: IdempotencyManager
    ) -> None:
        """Should remove listener with off()."""
        events: List[CacheRequestEvent] = []
        listener = lambda e: events.append(e)

        manager.on(listener)
        await manager.store("key1", "value1")
        count_after_first = len(events)

        manager.off(listener)
        await manager.store("key2", "value2")

        assert len(events) == count_after_first

    async def test_listener_errors_handled_gracefully(
        self, manager: IdempotencyManager
    ) -> None:
        """Should handle listener errors gracefully."""

        def error_listener(event: CacheRequestEvent) -> None:
            raise Exception("Listener error")

        manager.on(error_listener)

        # Should not throw
        await manager.store("key", "value")

    # === Boundary conditions ===

    async def test_boundary_empty_key(
        self, manager: IdempotencyManager
    ) -> None:
        """Should handle empty key."""
        await manager.store("", "value")
        check = await manager.check("")
        assert check.cached is True

    async def test_boundary_very_long_key(
        self, manager: IdempotencyManager
    ) -> None:
        """Should handle very long key."""
        long_key = "a" * 10000
        await manager.store(long_key, "value")
        check = await manager.check(long_key)
        assert check.cached is True

    async def test_boundary_special_chars_in_key(
        self, manager: IdempotencyManager
    ) -> None:
        """Should handle special characters in key."""
        special_key = "key:with/special@chars#and$symbols"
        await manager.store(special_key, "value")
        check = await manager.check(special_key)
        assert check.cached is True

    async def test_boundary_none_value(
        self, manager: IdempotencyManager
    ) -> None:
        """Should handle None value."""
        await manager.store("none-key", None)
        check = await manager.check("none-key")
        assert check.cached is True
        assert check.response is not None
        assert check.response.value is None

    async def test_boundary_complex_objects(
        self, manager: IdempotencyManager
    ) -> None:
        """Should handle complex objects."""
        complex_value = {
            "nested": {"deeply": {"value": [1, 2, 3]}},
            "number": 12345,
            "boolean": True,
        }

        await manager.store("complex-key", complex_value)
        check = await manager.check("complex-key")

        assert check.response is not None
        assert check.response.value == complex_value

    # === Concurrent operations ===

    async def test_concurrent_stores(
        self, manager: IdempotencyManager
    ) -> None:
        """Should handle concurrent stores."""
        async def store_key(i: int) -> None:
            await manager.store(f"concurrent-key-{i}", f"value-{i}")

        await asyncio.gather(*[store_key(i) for i in range(100)])

        stats = await manager.get_stats()
        assert stats["size"] == 100

    async def test_concurrent_checks(
        self, manager: IdempotencyManager
    ) -> None:
        """Should handle concurrent checks."""
        await manager.store("shared-key", "value")

        results = await asyncio.gather(*[manager.check("shared-key") for _ in range(100)])

        assert all(r.cached for r in results)

    # === State transitions ===

    async def test_state_new_to_stored_to_invalidated(
        self, manager: IdempotencyManager
    ) -> None:
        """Should transition: new -> stored -> invalidated -> new."""
        key = "state-key"

        # New state
        check = await manager.check(key)
        assert check.cached is False

        # Stored state
        await manager.store(key, "value")
        check = await manager.check(key)
        assert check.cached is True

        # Invalidated state
        await manager.invalidate(key)
        check = await manager.check(key)
        assert check.cached is False

    async def test_state_stored_to_expired(self) -> None:
        """Should transition: stored -> expired -> new."""
        manager = IdempotencyManager(IdempotencyConfig(ttl_seconds=0.01))
        key = "expire-state-key"

        await manager.store(key, "value")
        check = await manager.check(key)
        assert check.cached is True

        await asyncio.sleep(0.02)

        check = await manager.check(key)
        assert check.cached is False

        await manager.close()


class TestIdempotencyConflictError:
    """Tests for IdempotencyConflictError."""

    def test_error_properties(self) -> None:
        """Should have correct properties."""
        error = IdempotencyConflictError("Test message")

        assert error.args[0] == "Test message"
        assert error.code == "IDEMPOTENCY_CONFLICT"
        assert error.name == "IdempotencyConflictError"
        assert isinstance(error, Exception)


class TestConfigurationHelpers:
    """Tests for configuration helper functions."""

    def test_default_config_values(self) -> None:
        """Should have correct default values."""
        assert DEFAULT_IDEMPOTENCY_CONFIG.header_name == "Idempotency-Key"
        assert DEFAULT_IDEMPOTENCY_CONFIG.ttl_seconds == 86400
        assert DEFAULT_IDEMPOTENCY_CONFIG.auto_generate is True
        assert DEFAULT_IDEMPOTENCY_CONFIG.methods == ["POST", "PATCH"]
        assert callable(DEFAULT_IDEMPOTENCY_CONFIG.key_generator)

    def test_merge_config_with_none(self) -> None:
        """Should return defaults when no config provided."""
        merged = merge_idempotency_config(None)
        assert merged.header_name == "Idempotency-Key"
        assert merged.ttl_seconds == 86400

    def test_merge_config_with_partial(self) -> None:
        """Should merge partial config with defaults."""
        merged = merge_idempotency_config(IdempotencyConfig(ttl_seconds=3600))
        assert merged.header_name == "Idempotency-Key"
        assert merged.ttl_seconds == 3600

    def test_merge_config_preserves_custom(self) -> None:
        """Should preserve all custom values."""
        custom = IdempotencyConfig(
            header_name="X-Custom",
            ttl_seconds=1000,
            auto_generate=False,
            methods=["PUT"],
        )
        merged = merge_idempotency_config(custom)

        assert merged.header_name == "X-Custom"
        assert merged.ttl_seconds == 1000
        assert merged.auto_generate is False
        assert merged.methods == ["PUT"]

    def test_generate_fingerprint_method_and_url(self) -> None:
        """Should generate fingerprint from method and url."""
        fingerprint = generate_fingerprint(
            RequestFingerprint(method="POST", url="/api/users")
        )
        assert fingerprint == "POST|/api/users"

    def test_generate_fingerprint_with_body(self) -> None:
        """Should include body in fingerprint."""
        fingerprint = generate_fingerprint(
            RequestFingerprint(
                method="POST", url="/api/users", body=b'{"name":"test"}'
            )
        )
        assert fingerprint == 'POST|/api/users|{"name":"test"}'

    def test_generate_fingerprint_handles_none_body(self) -> None:
        """Should handle None body."""
        fingerprint = generate_fingerprint(
            RequestFingerprint(method="GET", url="/api/users", body=None)
        )
        assert fingerprint == "GET|/api/users"


class TestFactoryFunction:
    """Tests for create_idempotency_manager factory."""

    async def test_creates_manager_with_default_config(self) -> None:
        """Should create manager with default config."""
        manager = create_idempotency_manager()
        assert isinstance(manager, IdempotencyManager)
        await manager.close()

    async def test_creates_manager_with_custom_config(self) -> None:
        """Should create manager with custom config."""
        manager = create_idempotency_manager(IdempotencyConfig(ttl_seconds=1000))
        assert manager.get_config().ttl_seconds == 1000
        await manager.close()

    async def test_creates_manager_with_custom_store(self) -> None:
        """Should create manager with custom store."""
        store = MemoryCacheStore()
        manager = create_idempotency_manager(store=store)
        assert isinstance(manager, IdempotencyManager)
        await manager.close()
