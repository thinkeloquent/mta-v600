"""
Tests for fetch_compose_retry factory functions.

Test coverage includes:
- Statement coverage: All executable statements
- Decision/Branch coverage: All boolean decisions
- Equivalence partitioning: Different configuration combinations
- Boundary testing: Default values and overrides
"""

import pytest
from unittest.mock import MagicMock, patch
import httpx

from fetch_compose_retry.factory import (
    compose_transport,
    compose_sync_transport,
    create_retry_client,
    create_retry_sync_client,
    create_api_retry_transport,
    RETRY_PRESETS,
)
from fetch_compose_retry.transport import RetryTransport, SyncRetryTransport
from fetch_retry import RetryConfig


class TestComposeTransport:
    """Tests for compose_transport function."""

    def test_returns_base_when_no_wrappers(self):
        """Should return base transport when no wrappers provided."""
        base = MagicMock(spec=httpx.AsyncHTTPTransport)
        result = compose_transport(base)
        assert result == base

    def test_applies_single_wrapper(self):
        """Should apply single wrapper."""
        base = MagicMock(spec=httpx.AsyncHTTPTransport)
        wrapper = MagicMock(return_value="wrapped")
        result = compose_transport(base, wrapper)
        wrapper.assert_called_once_with(base)
        assert result == "wrapped"

    def test_applies_multiple_wrappers_in_order(self):
        """Should apply multiple wrappers in order."""
        base = MagicMock(spec=httpx.AsyncHTTPTransport)

        call_order = []

        def wrapper1(inner):
            call_order.append("wrapper1")
            return f"wrapped1({inner})"

        def wrapper2(inner):
            call_order.append("wrapper2")
            return f"wrapped2({inner})"

        result = compose_transport(base, wrapper1, wrapper2)

        assert call_order == ["wrapper1", "wrapper2"]
        assert "wrapped2" in result
        assert "wrapped1" in result


class TestComposeSyncTransport:
    """Tests for compose_sync_transport function."""

    def test_returns_base_when_no_wrappers(self):
        """Should return base transport when no wrappers provided."""
        base = MagicMock(spec=httpx.HTTPTransport)
        result = compose_sync_transport(base)
        assert result == base

    def test_applies_single_wrapper(self):
        """Should apply single wrapper."""
        base = MagicMock(spec=httpx.HTTPTransport)
        wrapper = MagicMock(return_value="wrapped")
        result = compose_sync_transport(base, wrapper)
        wrapper.assert_called_once_with(base)
        assert result == "wrapped"


class TestCreateRetryClient:
    """Tests for create_retry_client function."""

    def test_creates_async_client(self):
        """Should create async httpx.Client."""
        client = create_retry_client()
        assert isinstance(client, httpx.AsyncClient)

    def test_creates_client_with_custom_max_retries(self):
        """Should create client with custom max_retries."""
        client = create_retry_client(max_retries=5)
        assert isinstance(client, httpx.AsyncClient)
        # Transport is wrapped, verify the client was created
        assert client._transport is not None

    def test_creates_client_with_custom_config(self):
        """Should create client with custom config."""
        config = RetryConfig(max_retries=10, base_delay_seconds=2.0)
        client = create_retry_client(config=config)
        assert isinstance(client, httpx.AsyncClient)

    def test_creates_client_with_base_url(self):
        """Should create client with base_url."""
        client = create_retry_client(base_url="https://api.example.com")
        assert str(client.base_url) == "https://api.example.com"

    def test_creates_client_with_timeout(self):
        """Should create client with custom timeout."""
        client = create_retry_client(timeout=30.0)
        assert client.timeout.connect == 30.0

    def test_creates_client_with_callbacks(self):
        """Should create client with callbacks."""
        on_retry = MagicMock()
        on_success = MagicMock()
        client = create_retry_client(on_retry=on_retry, on_success=on_success)
        assert isinstance(client, httpx.AsyncClient)

    def test_passes_additional_client_kwargs(self):
        """Should pass additional kwargs to httpx.AsyncClient."""
        client = create_retry_client(follow_redirects=True)
        assert isinstance(client, httpx.AsyncClient)


class TestCreateRetrySyncClient:
    """Tests for create_retry_sync_client function."""

    def test_creates_sync_client(self):
        """Should create sync httpx.Client."""
        client = create_retry_sync_client()
        assert isinstance(client, httpx.Client)

    def test_creates_client_with_custom_max_retries(self):
        """Should create client with custom max_retries."""
        client = create_retry_sync_client(max_retries=5)
        assert isinstance(client, httpx.Client)

    def test_creates_client_with_custom_config(self):
        """Should create client with custom config."""
        config = RetryConfig(max_retries=10)
        client = create_retry_sync_client(config=config)
        assert isinstance(client, httpx.Client)

    def test_creates_client_with_base_url(self):
        """Should create client with base_url."""
        client = create_retry_sync_client(base_url="https://api.example.com")
        assert str(client.base_url) == "https://api.example.com"

    def test_creates_client_with_timeout(self):
        """Should create client with custom timeout."""
        client = create_retry_sync_client(timeout=30.0)
        assert client.timeout.connect == 30.0


class TestCreateApiRetryTransport:
    """Tests for create_api_retry_transport function."""

    def test_creates_transport_wrapper(self):
        """Should create transport wrapper function."""
        wrapper = create_api_retry_transport("github")
        assert callable(wrapper)

    def test_wrapper_creates_retry_transport(self):
        """Should create RetryTransport when wrapper is called."""
        wrapper = create_api_retry_transport("github", max_retries=5)
        inner = MagicMock(spec=httpx.AsyncHTTPTransport)
        transport = wrapper(inner)
        assert isinstance(transport, RetryTransport)
        assert transport._config.max_retries == 5

    def test_wrapper_passes_config(self):
        """Should pass config to transport."""
        config = RetryConfig(max_retries=10)
        wrapper = create_api_retry_transport("test", config=config)
        inner = MagicMock(spec=httpx.AsyncHTTPTransport)
        transport = wrapper(inner)
        assert transport._config.max_retries == 10

    def test_wrapper_passes_on_retry(self):
        """Should pass on_retry callback to transport."""
        on_retry = MagicMock()
        wrapper = create_api_retry_transport("test", on_retry=on_retry)
        inner = MagicMock(spec=httpx.AsyncHTTPTransport)
        transport = wrapper(inner)
        assert transport._on_retry is not None


class TestRetryPresets:
    """Tests for RETRY_PRESETS."""

    class TestDefaultPreset:
        """Tests for default preset."""

        def test_has_expected_values(self):
            """Should have expected values."""
            preset = RETRY_PRESETS["default"]
            assert preset.max_retries == 3
            assert preset.base_delay_seconds == 1.0
            assert preset.max_delay_seconds == 30.0
            assert preset.jitter_factor == 0.5
            assert preset.retry_on_status == [429, 500, 502, 503, 504]

        def test_is_valid_retry_config(self):
            """Should be a valid RetryConfig."""
            preset = RETRY_PRESETS["default"]
            assert isinstance(preset, RetryConfig)

        def test_usable_with_create_retry_client(self):
            """Should be usable with create_retry_client."""
            client = create_retry_client(config=RETRY_PRESETS["default"])
            assert isinstance(client, httpx.AsyncClient)

    class TestAggressivePreset:
        """Tests for aggressive preset."""

        def test_has_expected_values(self):
            """Should have expected values."""
            preset = RETRY_PRESETS["aggressive"]
            assert preset.max_retries == 5
            assert preset.base_delay_seconds == 0.5
            assert preset.max_delay_seconds == 60.0
            assert preset.jitter_factor == 0.3
            assert 520 in preset.retry_on_status
            assert 521 in preset.retry_on_status

        def test_is_valid_retry_config(self):
            """Should be a valid RetryConfig."""
            preset = RETRY_PRESETS["aggressive"]
            assert isinstance(preset, RetryConfig)

    class TestQuickPreset:
        """Tests for quick preset."""

        def test_has_expected_values(self):
            """Should have expected values."""
            preset = RETRY_PRESETS["quick"]
            assert preset.max_retries == 2
            assert preset.base_delay_seconds == 0.2
            assert preset.max_delay_seconds == 2.0
            assert preset.jitter_factor == 0.5
            assert preset.retry_on_status == [429, 502, 503, 504]

        def test_is_valid_retry_config(self):
            """Should be a valid RetryConfig."""
            preset = RETRY_PRESETS["quick"]
            assert isinstance(preset, RetryConfig)

    class TestGentlePreset:
        """Tests for gentle preset."""

        def test_has_expected_values(self):
            """Should have expected values."""
            preset = RETRY_PRESETS["gentle"]
            assert preset.max_retries == 5
            assert preset.base_delay_seconds == 2.0
            assert preset.max_delay_seconds == 120.0
            assert preset.jitter_factor == 0.7
            assert preset.retry_on_status == [429]

        def test_is_valid_retry_config(self):
            """Should be a valid RetryConfig."""
            preset = RETRY_PRESETS["gentle"]
            assert isinstance(preset, RetryConfig)


class TestIntegration:
    """Integration tests for factory functions."""

    def test_compose_with_retry_transport(self):
        """Should compose base transport with retry."""
        base = MagicMock(spec=httpx.AsyncHTTPTransport)

        def retry_wrapper(inner):
            return RetryTransport(inner, max_retries=3)

        transport = compose_transport(base, retry_wrapper)
        assert isinstance(transport, RetryTransport)

    def test_multiple_api_transports(self):
        """Should create multiple API-specific transports."""
        github_wrapper = create_api_retry_transport("github", max_retries=5)
        openai_wrapper = create_api_retry_transport("openai", max_retries=3)

        github_transport = github_wrapper(MagicMock(spec=httpx.AsyncHTTPTransport))
        openai_transport = openai_wrapper(MagicMock(spec=httpx.AsyncHTTPTransport))

        assert github_transport._config.max_retries == 5
        assert openai_transport._config.max_retries == 3
