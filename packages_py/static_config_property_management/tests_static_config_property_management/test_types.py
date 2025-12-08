"""Tests for static config type definitions."""

import pytest
from pydantic import ValidationError

from static_config import (
    ConfigScope,
    ConfigProperty,
    ResolutionContext,
    ProviderConfig,
    ClientConfig,
    DisplayConfig,
    ProxyConfig,
    ServerConfig,
)


class TestConfigScope:
    """Tests for ConfigScope enum."""

    def test_scope_values(self):
        """Should have expected scope values."""
        assert ConfigScope.GLOBAL.value == "global"
        assert ConfigScope.SERVICE.value == "service"
        assert ConfigScope.TENANT.value == "tenant"


class TestConfigProperty:
    """Tests for ConfigProperty model."""

    def test_create_property(self):
        """Should create property with defaults."""
        prop = ConfigProperty(value="test-value")
        assert prop.value == "test-value"
        assert prop.scope == ConfigScope.GLOBAL
        assert prop.metadata == {}

    def test_create_property_with_scope(self):
        """Should create property with specific scope."""
        prop = ConfigProperty(
            scope=ConfigScope.TENANT,
            value="tenant-value",
            metadata={"key": "value"},
        )
        assert prop.scope == ConfigScope.TENANT
        assert prop.metadata == {"key": "value"}


class TestResolutionContext:
    """Tests for ResolutionContext model."""

    def test_empty_context(self):
        """Should create empty context."""
        ctx = ResolutionContext()
        assert ctx.tenant_id is None
        assert ctx.service_id is None

    def test_context_with_tenant(self):
        """Should create context with tenant."""
        ctx = ResolutionContext(tenant_id="tenant-123")
        assert ctx.tenant_id == "tenant-123"

    def test_context_with_both(self):
        """Should create context with tenant and service."""
        ctx = ResolutionContext(tenant_id="tenant-123", service_id="service-456")
        assert ctx.tenant_id == "tenant-123"
        assert ctx.service_id == "service-456"


class TestProviderConfig:
    """Tests for ProviderConfig model."""

    def test_empty_provider(self):
        """Should create empty provider config."""
        provider = ProviderConfig()
        assert provider.base_url is None
        assert provider.model is None
        assert provider.env_api_key is None

    def test_full_provider(self):
        """Should create full provider config."""
        provider = ProviderConfig(
            base_url="https://api.example.com",
            model="test-model",
            env_api_key="TEST_API_KEY",
        )
        assert provider.base_url == "https://api.example.com"
        assert provider.model == "test-model"
        assert provider.env_api_key == "TEST_API_KEY"


class TestClientConfig:
    """Tests for ClientConfig model."""

    def test_default_values(self):
        """Should have default values."""
        client = ClientConfig()
        assert client.timeout_seconds == 60.0
        assert client.timeout_ms == 60000
        assert client.max_connections == 10

    def test_custom_values(self):
        """Should accept custom values."""
        client = ClientConfig(
            timeout_seconds=30.0,
            max_connections=20,
        )
        assert client.timeout_seconds == 30.0
        assert client.max_connections == 20


class TestDisplayConfig:
    """Tests for DisplayConfig model."""

    def test_default_values(self):
        """Should have default values."""
        display = DisplayConfig()
        assert display.separator_char == "="
        assert display.thin_separator_char == "-"
        assert display.separator_length == 60


class TestProxyConfig:
    """Tests for ProxyConfig model."""

    def test_default_values(self):
        """Should have default values."""
        proxy = ProxyConfig()
        assert proxy.default_environment == "dev"
        assert proxy.cert_verify is False
        assert proxy.proxy_urls == {}


class TestServerConfig:
    """Tests for ServerConfig model."""

    def test_default_server_config(self):
        """Should create config with defaults."""
        server = ServerConfig()
        assert server.providers == {}
        assert server.default_provider == "gemini"
        assert isinstance(server.client, ClientConfig)
        assert isinstance(server.display, DisplayConfig)
        assert isinstance(server.proxy, ProxyConfig)

    def test_full_server_config(self):
        """Should create full server config."""
        server = ServerConfig(
            providers={
                "test": ProviderConfig(
                    base_url="https://test.api",
                    model="test-model",
                ),
            },
            default_provider="test",
            client=ClientConfig(timeout_seconds=30.0),
        )
        assert "test" in server.providers
        assert server.default_provider == "test"
        assert server.client.timeout_seconds == 30.0

    def test_model_validate(self):
        """Should validate from dict."""
        data = {
            "providers": {
                "gemini": {
                    "base_url": "https://api.gemini.test",
                    "model": "gemini-2.0",
                },
            },
            "default_provider": "gemini",
            "client": {
                "timeout_seconds": 45.0,
            },
        }
        server = ServerConfig.model_validate(data)
        assert server.providers["gemini"].base_url == "https://api.gemini.test"
        assert server.client.timeout_seconds == 45.0
