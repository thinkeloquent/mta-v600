"""
Tests for config.py
Logic testing: Decision/Branch, Boundary Value, Error Path coverage
"""
import pytest

from fetch_client.config import (
    normalize_timeout,
    validate_config,
    validate_auth_config,
    get_auth_header_name,
    format_auth_header_value,
    resolve_config,
    DEFAULT_TIMEOUT,
    DEFAULT_CONTENT_TYPE,
    DefaultSerializer,
    AuthConfig,
    ClientConfig,
    TimeoutConfig,
)


class TestNormalizeTimeout:
    """Tests for normalize_timeout function."""

    # Decision: None returns DEFAULT_TIMEOUT
    def test_normalize_timeout_none(self):
        result = normalize_timeout(None)
        assert result == DEFAULT_TIMEOUT

    # Decision: float converts to TimeoutConfig
    def test_normalize_timeout_float(self):
        result = normalize_timeout(5.0)
        assert result.connect == 5.0
        assert result.read == 5.0
        assert result.write == 5.0

    # Decision: int converts to TimeoutConfig
    def test_normalize_timeout_int(self):
        result = normalize_timeout(10)
        assert result.connect == 10
        assert result.read == 10
        assert result.write == 10

    # Decision: TimeoutConfig returned as-is
    def test_normalize_timeout_object(self):
        config = TimeoutConfig(connect=1.0, read=2.0, write=3.0)
        result = normalize_timeout(config)
        assert result == config

    # Boundary: zero is valid
    def test_normalize_timeout_zero(self):
        result = normalize_timeout(0)
        assert result.connect == 0
        assert result.read == 0
        assert result.write == 0


class TestValidateConfig:
    """Tests for validate_config function."""

    # Error Path: empty base_url
    def test_validate_config_empty_base_url(self):
        config = ClientConfig(base_url="")
        with pytest.raises(ValueError, match="base_url is required"):
            validate_config(config)

    # Error Path: invalid URL format
    def test_validate_config_invalid_url(self):
        config = ClientConfig(base_url="not-a-url")
        with pytest.raises(ValueError, match="Invalid base_url"):
            validate_config(config)

    # Error Path: URL without scheme
    def test_validate_config_url_without_scheme(self):
        config = ClientConfig(base_url="api.example.com")
        with pytest.raises(ValueError, match="Invalid base_url"):
            validate_config(config)

    # Happy Path: valid http URL
    def test_validate_config_valid_http_url(self):
        config = ClientConfig(base_url="http://api.example.com")
        validate_config(config)  # Should not raise

    # Happy Path: valid https URL
    def test_validate_config_valid_https_url(self):
        config = ClientConfig(base_url="https://api.example.com")
        validate_config(config)  # Should not raise

    # Path: with auth, delegates to validate_auth_config
    def test_validate_config_with_invalid_auth(self):
        config = ClientConfig(
            base_url="https://api.example.com",
            auth=AuthConfig(type="invalid"),  # type: ignore
        )
        with pytest.raises(ValueError, match="Invalid auth type"):
            validate_config(config)

    # Path: without auth, skips auth validation
    def test_validate_config_without_auth(self):
        config = ClientConfig(base_url="https://api.example.com")
        validate_config(config)  # Should not raise


class TestValidateAuthConfig:
    """Tests for validate_auth_config function."""

    # Decision: bearer type with raw_api_key passes
    def test_validate_auth_config_bearer(self):
        auth = AuthConfig(type="bearer", raw_api_key="key")
        validate_auth_config(auth)  # Should not raise

    # Decision: x-api-key type with raw_api_key passes
    def test_validate_auth_config_x_api_key(self):
        auth = AuthConfig(type="x-api-key", raw_api_key="key")
        validate_auth_config(auth)  # Should not raise

    # Decision: custom type with header_name and raw_api_key passes
    def test_validate_auth_config_custom_valid(self):
        auth = AuthConfig(type="custom", header_name="X-Custom-Auth", raw_api_key="key")
        validate_auth_config(auth)  # Should not raise

    # Error Path: custom type without header_name
    def test_validate_auth_config_custom_no_header(self):
        auth = AuthConfig(type="custom", raw_api_key="key")
        with pytest.raises(ValueError, match="header_name is required"):
            validate_auth_config(auth)

    # Error Path: invalid type
    def test_validate_auth_config_invalid_type(self):
        auth = AuthConfig(type="invalid")  # type: ignore
        with pytest.raises(ValueError, match="Invalid auth type"):
            validate_auth_config(auth)


class TestGetAuthHeaderName:
    """Tests for get_auth_header_name function."""

    # Decision: bearer -> Authorization
    def test_get_auth_header_name_bearer(self):
        auth = AuthConfig(type="bearer")
        assert get_auth_header_name(auth) == "Authorization"

    # Decision: x-api-key -> X-API-Key (canonical form)
    def test_get_auth_header_name_x_api_key(self):
        auth = AuthConfig(type="x-api-key", raw_api_key="key")
        # get_auth_header_name returns canonical form
        assert get_auth_header_name(auth) == "X-API-Key"

    # Decision: custom -> custom header_name
    def test_get_auth_header_name_custom(self):
        auth = AuthConfig(type="custom", header_name="X-My-Header")
        assert get_auth_header_name(auth) == "X-My-Header"

    # Decision: custom without header_name -> fallback Authorization
    def test_get_auth_header_name_custom_no_header(self):
        auth = AuthConfig(type="custom")
        assert get_auth_header_name(auth) == "Authorization"

    # Decision: default case
    def test_get_auth_header_name_unknown(self):
        auth = AuthConfig(type="unknown")  # type: ignore
        assert get_auth_header_name(auth) == "Authorization"


class TestFormatAuthHeaderValue:
    """Tests for format_auth_header_value function."""

    # Decision: bearer -> Bearer prefix
    def test_format_auth_header_value_bearer(self):
        auth = AuthConfig(type="bearer")
        assert format_auth_header_value(auth, "test-key") == "Bearer test-key"

    # Decision: x-api-key -> raw key
    def test_format_auth_header_value_x_api_key(self):
        auth = AuthConfig(type="x-api-key")
        assert format_auth_header_value(auth, "test-key") == "test-key"

    # Decision: custom -> raw key
    def test_format_auth_header_value_custom(self):
        auth = AuthConfig(type="custom", header_name="X-Auth")
        assert format_auth_header_value(auth, "test-key") == "test-key"

    # Boundary: empty api_key for bearer
    def test_format_auth_header_value_empty_key(self):
        auth = AuthConfig(type="bearer")
        assert format_auth_header_value(auth, "") == "Bearer "


class TestResolveConfig:
    """Tests for resolve_config function."""

    # Path: full config resolution
    def test_resolve_config_with_defaults(self):
        config = ClientConfig(base_url="https://api.example.com")
        result = resolve_config(config)

        assert result.base_url == "https://api.example.com"
        assert result.timeout == DEFAULT_TIMEOUT
        assert result.headers == {}
        assert result.content_type == DEFAULT_CONTENT_TYPE
        assert result.auth is None

    # Path: with custom timeout
    def test_resolve_config_with_custom_timeout(self):
        config = ClientConfig(base_url="https://api.example.com", timeout=10.0)
        result = resolve_config(config)

        assert result.timeout.connect == 10.0
        assert result.timeout.read == 10.0
        assert result.timeout.write == 10.0

    # Path: with custom headers
    def test_resolve_config_with_headers(self):
        headers = {"User-Agent": "TestClient/1.0"}
        config = ClientConfig(base_url="https://api.example.com", headers=headers)
        result = resolve_config(config)

        assert result.headers == headers
        # Should be a copy
        assert result.headers is not headers

    # Path: with custom content_type
    def test_resolve_config_with_custom_content_type(self):
        config = ClientConfig(
            base_url="https://api.example.com", content_type="application/xml"
        )
        result = resolve_config(config)
        assert result.content_type == "application/xml"

    # Path: with auth config
    def test_resolve_config_with_auth(self):
        auth = AuthConfig(type="bearer", raw_api_key="secret")
        config = ClientConfig(base_url="https://api.example.com", auth=auth)
        result = resolve_config(config)
        assert result.auth == auth

    # Error Path: propagates validation errors
    def test_resolve_config_invalid(self):
        config = ClientConfig(base_url="")
        with pytest.raises(ValueError, match="base_url is required"):
            resolve_config(config)


class TestDefaultSerializer:
    """Tests for DefaultSerializer class."""

    def test_serialize_object(self):
        serializer = DefaultSerializer()
        obj = {"name": "test", "value": 123}
        result = serializer.serialize(obj)
        assert result == '{"name": "test", "value": 123}'

    def test_deserialize_json(self):
        serializer = DefaultSerializer()
        json_str = '{"name": "test", "value": 123}'
        result = serializer.deserialize(json_str)
        assert result == {"name": "test", "value": 123}

    def test_nested_objects(self):
        serializer = DefaultSerializer()
        nested = {"outer": {"inner": [1, 2, 3]}}
        serialized = serializer.serialize(nested)
        deserialized = serializer.deserialize(serialized)
        assert deserialized == nested

    def test_deserialize_invalid_json(self):
        serializer = DefaultSerializer()
        with pytest.raises(Exception):
            serializer.deserialize("not json")

    def test_serialize_null(self):
        serializer = DefaultSerializer()
        assert serializer.serialize(None) == "null"

    def test_deserialize_null(self):
        serializer = DefaultSerializer()
        assert serializer.deserialize("null") is None


class TestDefaultValues:
    """Tests for default values."""

    def test_default_timeout(self):
        assert DEFAULT_TIMEOUT.connect == 5.0
        assert DEFAULT_TIMEOUT.read == 30.0
        assert DEFAULT_TIMEOUT.write == 10.0

    def test_default_content_type(self):
        assert DEFAULT_CONTENT_TYPE == "application/json"
