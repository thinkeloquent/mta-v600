"""
Comprehensive tests for provider_api_getters.api_token.base module.

Tests cover:
- Decision/Branch coverage for all control flow
- Boundary value analysis
- State transition testing
- Log verification for defensive programming
"""
import logging
import pytest
from typing import Any, Dict

from provider_api_getters.api_token.base import (
    RequestContext,
    ApiKeyResult,
    BaseApiToken,
    VALID_AUTH_TYPES,
    _mask_sensitive,
)

# Enable debug logging for tests
logging.getLogger("provider_api_getters").setLevel(logging.DEBUG)


class TestMaskSensitive:
    """Tests for _mask_sensitive helper function."""

    # Equivalence Partitioning: None, empty, short, normal, long strings

    def test_mask_none_value(self):
        """Test masking None value returns <None>."""
        result = _mask_sensitive(None)
        assert result == "<None>"

    def test_mask_non_string_value(self):
        """Test masking non-string value returns <invalid-type>."""
        result = _mask_sensitive(123)  # type: ignore
        assert result == "<invalid-type>"

    def test_mask_empty_string(self):
        """Test masking empty string returns empty stars."""
        result = _mask_sensitive("")
        assert result == ""

    def test_mask_short_string_equal_to_visible(self):
        """Test masking string equal to visible_chars."""
        result = _mask_sensitive("1234", visible_chars=4)
        assert result == "****"

    def test_mask_short_string_less_than_visible(self):
        """Test masking string shorter than visible_chars."""
        result = _mask_sensitive("abc", visible_chars=4)
        assert result == "***"

    def test_mask_normal_string(self):
        """Test masking normal length string."""
        result = _mask_sensitive("secret_token_12345", visible_chars=4)
        assert result == "secr**************"
        assert len(result) == 18

    def test_mask_custom_visible_chars(self):
        """Test masking with custom visible_chars."""
        result = _mask_sensitive("abcdefgh", visible_chars=2)
        assert result == "ab******"


class TestRequestContext:
    """Tests for RequestContext dataclass."""

    def test_default_initialization(self, caplog):
        """Test default initialization with all None values."""
        with caplog.at_level(logging.DEBUG):
            ctx = RequestContext()

        assert ctx.request is None
        assert ctx.app_state is None
        assert ctx.tenant_id is None
        assert ctx.user_id is None
        assert ctx.extra == {}

        # Verify log was emitted
        assert "RequestContext.__post_init__" in caplog.text

    def test_initialization_with_values(self, caplog):
        """Test initialization with provided values."""
        mock_request = object()
        mock_state = {"key": "value"}

        with caplog.at_level(logging.DEBUG):
            ctx = RequestContext(
                request=mock_request,
                app_state=mock_state,
                tenant_id="tenant-123",
                user_id="user-456",
                extra={"custom": "data"},
            )

        assert ctx.request is mock_request
        assert ctx.app_state == mock_state
        assert ctx.tenant_id == "tenant-123"
        assert ctx.user_id == "user-456"
        assert ctx.extra == {"custom": "data"}

    def test_extra_none_defaults_to_empty_dict(self, caplog):
        """Test that None extra value is normalized to empty dict."""
        with caplog.at_level(logging.DEBUG):
            ctx = RequestContext(extra=None)  # type: ignore

        assert ctx.extra == {}
        assert "extra was None, defaulting to empty dict" in caplog.text

    def test_tenant_id_type_coercion(self, caplog):
        """Test that non-string tenant_id is coerced to string."""
        with caplog.at_level(logging.WARNING):
            ctx = RequestContext(tenant_id=12345)  # type: ignore

        assert ctx.tenant_id == "12345"
        assert "tenant_id is not a string" in caplog.text

    def test_user_id_type_coercion(self, caplog):
        """Test that non-string user_id is coerced to string."""
        with caplog.at_level(logging.WARNING):
            ctx = RequestContext(user_id=99999)  # type: ignore

        assert ctx.user_id == "99999"
        assert "user_id is not a string" in caplog.text

    def test_to_dict_serialization(self, caplog):
        """Test to_dict serialization."""
        ctx = RequestContext(
            request=object(),
            app_state={"key": "value"},
            tenant_id="t1",
            user_id="u1",
            extra={"a": 1, "b": 2},
        )

        with caplog.at_level(logging.DEBUG):
            result = ctx.to_dict()

        assert result == {
            "tenant_id": "t1",
            "user_id": "u1",
            "has_request": True,
            "has_app_state": True,
            "extra_keys": ["a", "b"],
        }
        assert "Converting context to dictionary" in caplog.text

    def test_to_dict_with_none_values(self):
        """Test to_dict with None values."""
        ctx = RequestContext()
        result = ctx.to_dict()

        assert result["tenant_id"] is None
        assert result["user_id"] is None
        assert result["has_request"] is False
        assert result["has_app_state"] is False
        assert result["extra_keys"] == []


class TestApiKeyResult:
    """Tests for ApiKeyResult dataclass."""

    def test_default_initialization(self, caplog):
        """Test default initialization."""
        with caplog.at_level(logging.DEBUG):
            result = ApiKeyResult()

        assert result.api_key is None
        assert result.auth_type == "bearer"
        assert result.header_name == "Authorization"
        assert result.username is None
        assert result.client is None
        assert result.is_placeholder is False
        assert result.placeholder_message is None
        assert "ApiKeyResult.__post_init__" in caplog.text

    def test_initialization_with_api_key(self, caplog):
        """Test initialization with API key."""
        with caplog.at_level(logging.DEBUG):
            result = ApiKeyResult(
                api_key="test-key-12345",
                auth_type="bearer",
            )

        assert result.api_key == "test-key-12345"
        assert result.has_credentials is True

    def test_invalid_auth_type_logs_warning(self, caplog):
        """Test that invalid auth_type logs a warning."""
        with caplog.at_level(logging.WARNING):
            result = ApiKeyResult(auth_type="invalid-type")

        assert f"Invalid auth_type 'invalid-type'" in caplog.text
        assert f"expected one of {VALID_AUTH_TYPES}" in caplog.text

    def test_valid_auth_types(self):
        """Test all valid auth types."""
        for auth_type in VALID_AUTH_TYPES:
            result = ApiKeyResult(auth_type=auth_type)
            assert result.auth_type == auth_type

    def test_empty_header_name_defaults_to_authorization(self, caplog):
        """Test that empty header_name defaults to Authorization."""
        with caplog.at_level(logging.DEBUG):
            result = ApiKeyResult(header_name="")

        assert result.header_name == "Authorization"
        assert "header_name is empty, defaulting to Authorization" in caplog.text

    def test_placeholder_with_api_key_logs_warning(self, caplog):
        """Test that placeholder with api_key logs inconsistency warning."""
        with caplog.at_level(logging.WARNING):
            result = ApiKeyResult(
                api_key="some-key",
                is_placeholder=True,
            )

        assert "is_placeholder=True but api_key is set" in caplog.text

    # Decision/Branch coverage for has_credentials property

    def test_has_credentials_when_placeholder(self, caplog):
        """Test has_credentials returns False when is_placeholder is True."""
        result = ApiKeyResult(is_placeholder=True)

        with caplog.at_level(logging.DEBUG):
            has_creds = result.has_credentials

        assert has_creds is False
        assert "is_placeholder=True, returning False" in caplog.text

    def test_has_credentials_when_client_set(self, caplog):
        """Test has_credentials returns True when client is set."""
        result = ApiKeyResult(client=object())

        with caplog.at_level(logging.DEBUG):
            has_creds = result.has_credentials

        assert has_creds is True
        assert "client is set, returning True" in caplog.text

    def test_has_credentials_when_api_key_set(self, caplog):
        """Test has_credentials returns True when api_key is set."""
        result = ApiKeyResult(api_key="test-key")

        with caplog.at_level(logging.DEBUG):
            has_creds = result.has_credentials

        assert has_creds is True
        assert "api_key check result=True" in caplog.text

    def test_has_credentials_when_nothing_set(self, caplog):
        """Test has_credentials returns False when nothing is set."""
        result = ApiKeyResult()

        with caplog.at_level(logging.DEBUG):
            has_creds = result.has_credentials

        assert has_creds is False
        assert "api_key check result=False" in caplog.text

    def test_to_dict_without_sensitive(self, caplog):
        """Test to_dict without sensitive data."""
        result = ApiKeyResult(
            api_key="secret",
            auth_type="bearer",
            username="user@example.com",
        )

        with caplog.at_level(logging.DEBUG):
            d = result.to_dict(include_sensitive=False)

        assert "api_key_masked" not in d
        assert "username" not in d
        assert d["auth_type"] == "bearer"
        assert d["has_api_key"] is True
        assert d["has_username"] is True

    def test_to_dict_with_sensitive(self, caplog):
        """Test to_dict with sensitive data included."""
        result = ApiKeyResult(
            api_key="secret-token",
            username="user@example.com",
        )

        with caplog.at_level(logging.DEBUG):
            d = result.to_dict(include_sensitive=True)

        assert "api_key_masked" in d
        assert d["api_key_masked"] == "secr********"  # 12 chars total, 4 visible + 8 masked
        assert d["username"] == "user@example.com"


class ConcreteApiToken(BaseApiToken):
    """Concrete implementation for testing BaseApiToken."""

    def __init__(self, config_store=None, name: str = "test"):
        super().__init__(config_store)
        self._name = name

    @property
    def provider_name(self) -> str:
        return self._name

    def get_api_key(self) -> ApiKeyResult:
        api_key = self._lookup_env_api_key()
        return ApiKeyResult(api_key=api_key)


class TestBaseApiToken:
    """Tests for BaseApiToken abstract class."""

    def test_initialization_with_config_store(self, mock_config_store, caplog):
        """Test initialization with provided config_store."""
        with caplog.at_level(logging.DEBUG):
            token = ConcreteApiToken(config_store=mock_config_store)

        assert token._config_store is mock_config_store
        assert "Initializing with config_store=provided" in caplog.text

    def test_initialization_without_config_store(self, caplog):
        """Test initialization without config_store."""
        with caplog.at_level(logging.DEBUG):
            token = ConcreteApiToken()

        assert token._config_store is None
        assert "will lazy-load" in caplog.text

    def test_config_store_lazy_loading(self, caplog, mocker):
        """Test lazy loading of config_store."""
        # Mock the static_config module
        mock_config = mocker.MagicMock()
        mock_config.is_initialized.return_value = True
        mocker.patch.dict(
            "sys.modules",
            {"static_config": mocker.MagicMock(config=mock_config)}
        )

        token = ConcreteApiToken()

        with caplog.at_level(logging.DEBUG):
            _ = token.config_store

        assert "lazy-loading from static_config module" in caplog.text

    def test_get_provider_config_with_valid_config(self, caplog):
        """Test _get_provider_config with valid configuration."""
        config = {
            "providers": {
                "test": {
                    "base_url": "https://api.test.com",
                    "env_api_key": "TEST_TOKEN",
                }
            }
        }
        from .conftest import MockConfigStore
        mock_store = MockConfigStore(config)
        token = ConcreteApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = token._get_provider_config()

        assert result["base_url"] == "https://api.test.com"
        assert "Found config with keys" in caplog.text

    def test_get_provider_config_with_missing_config(self, caplog):
        """Test _get_provider_config with missing configuration."""
        from .conftest import MockConfigStore
        mock_store = MockConfigStore({"providers": {}})
        token = ConcreteApiToken(config_store=mock_store)

        with caplog.at_level(logging.WARNING):
            result = token._get_provider_config()

        assert result == {}
        assert "No config found for provider" in caplog.text

    def test_get_provider_config_caching(self, caplog):
        """Test that _get_provider_config caches results."""
        config = {"providers": {"test": {"key": "value"}}}
        from .conftest import MockConfigStore
        mock_store = MockConfigStore(config)
        token = ConcreteApiToken(config_store=mock_store)

        # First call
        with caplog.at_level(logging.DEBUG):
            result1 = token._get_provider_config()

        # Clear logs
        caplog.clear()

        # Second call should use cache
        with caplog.at_level(logging.DEBUG):
            result2 = token._get_provider_config()

        assert result1 == result2
        assert "Returning cached config" in caplog.text

    def test_get_provider_config_exception_handling(self, caplog, mocker):
        """Test _get_provider_config handles exceptions gracefully."""
        mock_store = mocker.MagicMock()
        mock_store.get_nested.side_effect = RuntimeError("Config error")
        token = ConcreteApiToken(config_store=mock_store)

        with caplog.at_level(logging.ERROR):
            result = token._get_provider_config()

        assert result == {}
        assert "Exception while getting config" in caplog.text
        assert "RuntimeError" in caplog.text

    def test_get_base_url_from_config(self, caplog):
        """Test _get_base_url when base_url is in config."""
        config = {"providers": {"test": {"base_url": "https://api.test.com"}}}
        from .conftest import MockConfigStore
        mock_store = MockConfigStore(config)
        token = ConcreteApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = token._get_base_url()

        assert result == "https://api.test.com"
        assert "Using base_url from config" in caplog.text

    def test_get_base_url_from_env(self, caplog, clean_env):
        """Test _get_base_url when base_url comes from environment."""
        clean_env(TEST_BASE_URL="https://env.test.com")

        config = {"providers": {"test": {"env_base_url": "TEST_BASE_URL"}}}
        from .conftest import MockConfigStore
        mock_store = MockConfigStore(config)
        token = ConcreteApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = token._get_base_url()

        assert result == "https://env.test.com"
        assert "Using base_url from env var" in caplog.text

    def test_get_base_url_env_not_set(self, caplog, clean_env):
        """Test _get_base_url when env var is not set."""
        config = {"providers": {"test": {"env_base_url": "UNSET_VAR"}}}
        from .conftest import MockConfigStore
        mock_store = MockConfigStore(config)
        token = ConcreteApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = token._get_base_url()

        assert result is None
        assert "is not set" in caplog.text

    def test_get_base_url_nothing_configured(self, caplog):
        """Test _get_base_url when nothing is configured."""
        from .conftest import MockConfigStore
        mock_store = MockConfigStore({"providers": {"test": {}}})
        token = ConcreteApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = token._get_base_url()

        assert result is None
        assert "No base_url or env_base_url configured" in caplog.text

    def test_lookup_env_api_key_found(self, caplog, clean_env):
        """Test _lookup_env_api_key when key is found."""
        clean_env(TEST_TOKEN="my-secret-token")

        config = {"providers": {"test": {"env_api_key": "TEST_TOKEN"}}}
        from .conftest import MockConfigStore
        mock_store = MockConfigStore(config)
        token = ConcreteApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = token._lookup_env_api_key()

        assert result == "my-secret-token"
        assert "Found API key in env var" in caplog.text
        assert "my-s***********" in caplog.text  # Masked value (15 chars: 4 visible + 11 masked)

    def test_lookup_env_api_key_not_found(self, caplog, clean_env):
        """Test _lookup_env_api_key when key is not found."""
        config = {"providers": {"test": {"env_api_key": "MISSING_TOKEN"}}}
        from .conftest import MockConfigStore
        mock_store = MockConfigStore(config)
        token = ConcreteApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = token._lookup_env_api_key()

        assert result is None
        assert "is not set or empty" in caplog.text

    def test_lookup_env_api_key_no_config(self, caplog):
        """Test _lookup_env_api_key when no env_api_key configured."""
        from .conftest import MockConfigStore
        mock_store = MockConfigStore({"providers": {"test": {}}})
        token = ConcreteApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = token._lookup_env_api_key()

        assert result is None
        assert "No env_api_key configured" in caplog.text

    def test_health_endpoint_from_config(self, caplog):
        """Test health_endpoint when configured in config."""
        config = {"providers": {"test": {"health_endpoint": "/v2/health"}}}
        from .conftest import MockConfigStore
        mock_store = MockConfigStore(config)
        token = ConcreteApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = token.health_endpoint

        assert result == "/v2/health"
        assert "from_config=True" in caplog.text

    def test_health_endpoint_default(self, caplog):
        """Test health_endpoint uses default when not configured."""
        from .conftest import MockConfigStore
        mock_store = MockConfigStore({"providers": {"test": {}}})
        token = ConcreteApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = token.health_endpoint

        assert result == "/"
        assert "from_config=False" in caplog.text

    def test_get_api_key_for_request_default(self, caplog, clean_env):
        """Test get_api_key_for_request default behavior."""
        clean_env(TEST_TOKEN="request-token")

        config = {"providers": {"test": {"env_api_key": "TEST_TOKEN"}}}
        from .conftest import MockConfigStore
        mock_store = MockConfigStore(config)
        token = ConcreteApiToken(config_store=mock_store)

        ctx = RequestContext(tenant_id="t1", user_id="u1")

        with caplog.at_level(logging.DEBUG):
            result = token.get_api_key_for_request(ctx)

        assert result.api_key == "request-token"
        assert "tenant_id=t1 provided but base implementation" in caplog.text
        assert "user_id=u1 provided but base implementation" in caplog.text

    def test_validate_with_all_valid(self, caplog, clean_env):
        """Test validate returns valid when all requirements met."""
        clean_env(TEST_TOKEN="valid-token")

        config = {
            "providers": {
                "test": {
                    "base_url": "https://api.test.com",
                    "env_api_key": "TEST_TOKEN",
                }
            }
        }
        from .conftest import MockConfigStore
        mock_store = MockConfigStore(config)
        token = ConcreteApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = token.validate()

        assert result["valid"] is True
        assert result["issues"] == []
        assert result["has_base_url"] is True
        assert result["has_credentials"] is True

    def test_validate_with_missing_base_url(self, caplog, clean_env):
        """Test validate detects missing base_url."""
        clean_env(TEST_TOKEN="valid-token")

        config = {"providers": {"test": {"env_api_key": "TEST_TOKEN"}}}
        from .conftest import MockConfigStore
        mock_store = MockConfigStore(config)
        token = ConcreteApiToken(config_store=mock_store)

        result = token.validate()

        assert result["valid"] is False
        assert "No base_url configured" in result["issues"]

    def test_validate_with_missing_credentials(self, caplog, clean_env):
        """Test validate detects missing credentials."""
        config = {"providers": {"test": {"base_url": "https://api.test.com"}}}
        from .conftest import MockConfigStore
        mock_store = MockConfigStore(config)
        token = ConcreteApiToken(config_store=mock_store)

        result = token.validate()

        assert result["valid"] is False
        assert "No API credentials available" in result["issues"]

    def test_validate_with_placeholder(self, caplog):
        """Test validate handles placeholder providers."""

        class PlaceholderToken(BaseApiToken):
            @property
            def provider_name(self) -> str:
                return "placeholder"

            def get_api_key(self) -> ApiKeyResult:
                return ApiKeyResult(
                    is_placeholder=True,
                    placeholder_message="Not implemented"
                )

        from .conftest import MockConfigStore
        mock_store = MockConfigStore({
            "providers": {
                "placeholder": {"base_url": "https://placeholder.com"}
            }
        })
        token = PlaceholderToken(config_store=mock_store)

        result = token.validate()

        assert result["is_placeholder"] is True
        assert "Provider is placeholder: Not implemented" in result["warnings"]

    def test_clear_cache(self, caplog):
        """Test clear_cache resets the config cache."""
        config = {"providers": {"test": {"key": "value"}}}
        from .conftest import MockConfigStore
        mock_store = MockConfigStore(config)
        token = ConcreteApiToken(config_store=mock_store)

        # Populate cache
        token._get_provider_config()
        assert token._config_cache is not None

        with caplog.at_level(logging.DEBUG):
            token.clear_cache()

        assert token._config_cache is None
        assert "Clearing configuration cache" in caplog.text
