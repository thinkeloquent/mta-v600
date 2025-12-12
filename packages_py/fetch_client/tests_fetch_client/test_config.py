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
    """Tests for format_auth_header_value function.

    Covers all 13 auth types:
    - Basic family: basic, basic_email_token, basic_token, basic_email
    - Bearer family: bearer, bearer_oauth, bearer_jwt, bearer_username_token,
                     bearer_username_password, bearer_email_token, bearer_email_password
    - Custom/API Key: x-api-key, custom
    """
    import base64

    # =========================================================================
    # Helper for expected base64 values
    # =========================================================================
    @staticmethod
    def _encode_basic(identifier: str, secret: str) -> str:
        import base64
        credentials = f"{identifier}:{secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    @staticmethod
    def _encode_bearer_base64(identifier: str, secret: str) -> str:
        import base64
        credentials = f"{identifier}:{secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Bearer {encoded}"

    # =========================================================================
    # Basic Auth Family Tests
    # =========================================================================

    def test_basic_with_email_and_token(self):
        """basic auth with email + raw_api_key (token)"""
        auth = AuthConfig(type="basic", email="test@email.com", raw_api_key="token123")
        result = format_auth_header_value(auth, "token123")
        expected = self._encode_basic("test@email.com", "token123")
        assert result == expected

    def test_basic_with_username_and_token(self):
        """basic auth with username + raw_api_key (token)"""
        auth = AuthConfig(type="basic", username="testuser", raw_api_key="token123")
        result = format_auth_header_value(auth, "token123")
        expected = self._encode_basic("testuser", "token123")
        assert result == expected

    def test_basic_with_email_and_password(self):
        """basic auth with email + password (no raw_api_key)"""
        auth = AuthConfig(type="basic", email="test@email.com", password="pass123")
        result = format_auth_header_value(auth, "pass123")
        expected = self._encode_basic("test@email.com", "pass123")
        assert result == expected

    def test_basic_email_token(self):
        """basic_email_token: email + api_key → Basic <base64(email:token)>"""
        auth = AuthConfig(type="basic_email_token", email="user@atlassian.com", raw_api_key="api_token")
        result = format_auth_header_value(auth, "api_token")
        expected = self._encode_basic("user@atlassian.com", "api_token")
        assert result == expected

    def test_basic_token(self):
        """basic_token: username + api_key → Basic <base64(username:token)>"""
        auth = AuthConfig(type="basic_token", username="admin", raw_api_key="token456")
        result = format_auth_header_value(auth, "token456")
        expected = self._encode_basic("admin", "token456")
        assert result == expected

    def test_basic_email(self):
        """basic_email: email + password → Basic <base64(email:password)>"""
        auth = AuthConfig(type="basic_email", email="user@example.com", password="secret")
        result = format_auth_header_value(auth, "ignored")  # api_key is ignored, uses password
        expected = self._encode_basic("user@example.com", "secret")
        assert result == expected

    # =========================================================================
    # Bearer Auth Family Tests
    # =========================================================================

    def test_bearer_plain_token(self):
        """bearer auth with plain token (PAT, OAuth, JWT)"""
        auth = AuthConfig(type="bearer", raw_api_key="pat_token_123")
        result = format_auth_header_value(auth, "pat_token_123")
        assert result == "Bearer pat_token_123"

    def test_bearer_with_username_encodes_base64(self):
        """bearer auth with username uses base64 encoding"""
        auth = AuthConfig(type="bearer", username="user", raw_api_key="token")
        result = format_auth_header_value(auth, "token")
        expected = self._encode_bearer_base64("user", "token")
        assert result == expected

    def test_bearer_with_email_encodes_base64(self):
        """bearer auth with email uses base64 encoding"""
        auth = AuthConfig(type="bearer", email="user@test.com", raw_api_key="token")
        result = format_auth_header_value(auth, "token")
        expected = self._encode_bearer_base64("user@test.com", "token")
        assert result == expected

    def test_bearer_oauth(self):
        """bearer_oauth: OAuth 2.0 token as-is"""
        auth = AuthConfig(type="bearer_oauth", raw_api_key="ya29.oauth_token_abc123")
        result = format_auth_header_value(auth, "ya29.oauth_token_abc123")
        assert result == "Bearer ya29.oauth_token_abc123"

    def test_bearer_jwt(self):
        """bearer_jwt: JWT token as-is"""
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        auth = AuthConfig(type="bearer_jwt", raw_api_key=jwt)
        result = format_auth_header_value(auth, jwt)
        assert result == f"Bearer {jwt}"

    def test_bearer_username_token(self):
        """bearer_username_token: Bearer <base64(username:token)>"""
        auth = AuthConfig(type="bearer_username_token", username="apiuser", raw_api_key="token789")
        result = format_auth_header_value(auth, "token789")
        expected = self._encode_bearer_base64("apiuser", "token789")
        assert result == expected

    def test_bearer_username_password(self):
        """bearer_username_password: Bearer <base64(username:password)>"""
        auth = AuthConfig(type="bearer_username_password", username="admin", password="adminpass")
        result = format_auth_header_value(auth, "ignored")
        expected = self._encode_bearer_base64("admin", "adminpass")
        assert result == expected

    def test_bearer_email_token(self):
        """bearer_email_token: Bearer <base64(email:token)>"""
        auth = AuthConfig(type="bearer_email_token", email="user@corp.com", raw_api_key="email_token")
        result = format_auth_header_value(auth, "email_token")
        expected = self._encode_bearer_base64("user@corp.com", "email_token")
        assert result == expected

    def test_bearer_email_password(self):
        """bearer_email_password: Bearer <base64(email:password)>"""
        auth = AuthConfig(type="bearer_email_password", email="user@corp.com", password="emailpass")
        result = format_auth_header_value(auth, "ignored")
        expected = self._encode_bearer_base64("user@corp.com", "emailpass")
        assert result == expected

    # =========================================================================
    # Custom/API Key Auth Tests
    # =========================================================================

    def test_x_api_key(self):
        """x-api-key: raw key value"""
        auth = AuthConfig(type="x-api-key", raw_api_key="sk-1234567890abcdef")
        result = format_auth_header_value(auth, "sk-1234567890abcdef")
        assert result == "sk-1234567890abcdef"

    def test_custom(self):
        """custom: raw key with custom header"""
        auth = AuthConfig(type="custom", header_name="X-Custom-Auth", raw_api_key="custom_token")
        result = format_auth_header_value(auth, "custom_token")
        assert result == "custom_token"

    def test_custom_header(self):
        """custom_header: same as custom"""
        auth = AuthConfig(type="custom_header", header_name="X-Service-Key", raw_api_key="service_key_123")
        result = format_auth_header_value(auth, "service_key_123")
        assert result == "service_key_123"

    # =========================================================================
    # Double-Encoding Regression Tests (Bug Fix)
    # =========================================================================

    def test_already_encoded_basic_not_double_encoded(self):
        """Regression: pre-encoded Basic value should not be double-encoded"""
        # Simulate api_token returning pre-encoded value
        pre_encoded = "Basic dGVzdEBlbWFpbC5jb206dG9rZW4xMjM="  # test@email.com:token123
        auth = AuthConfig(type="bearer", raw_api_key=pre_encoded)  # Even with bearer type
        result = format_auth_header_value(auth, pre_encoded)
        # Should return as-is, NOT "Bearer Basic dGVzdEBlbWFpbC5jb206dG9rZW4xMjM="
        assert result == pre_encoded
        assert not result.startswith("Bearer Basic")

    def test_already_encoded_bearer_not_double_encoded(self):
        """Regression: pre-encoded Bearer value should not be double-encoded"""
        pre_encoded = "Bearer token123"
        auth = AuthConfig(type="bearer", raw_api_key=pre_encoded)
        result = format_auth_header_value(auth, pre_encoded)
        # Should return as-is, NOT "Bearer Bearer token123"
        assert result == pre_encoded
        assert result.count("Bearer") == 1

    def test_already_encoded_basic_with_basic_type(self):
        """Regression: pre-encoded Basic with basic auth type"""
        pre_encoded = "Basic dXNlcjpwYXNz"  # user:pass
        auth = AuthConfig(type="basic", email="user", raw_api_key=pre_encoded)
        result = format_auth_header_value(auth, pre_encoded)
        # Guard should catch the "Basic " prefix and return as-is
        assert result == pre_encoded

    def test_malformed_bearer_basic_prevented(self):
        """Regression: ensure 'Bearer Basic <base64>' malformation is prevented"""
        # This was the actual bug: api_token returned "Basic <base64>",
        # then health check passed it to AuthConfig(type="bearer") which
        # would produce "Bearer Basic <base64>"
        pre_encoded_basic = "Basic " + __import__('base64').b64encode(b"email:token").decode()
        auth = AuthConfig(type="bearer", raw_api_key=pre_encoded_basic)
        result = format_auth_header_value(auth, pre_encoded_basic)
        # Must NOT start with "Bearer Basic"
        assert not result.startswith("Bearer Basic")
        # Should return the pre-encoded Basic value as-is
        assert result == pre_encoded_basic

    # =========================================================================
    # Edge Cases and Boundary Values
    # =========================================================================

    def test_empty_api_key_bearer(self):
        """Boundary: empty api_key for bearer raises ValueError"""
        auth = AuthConfig(type="bearer")
        with pytest.raises(ValueError, match="bearer requires token"):
            format_auth_header_value(auth, "")

    def test_none_identifier_basic(self):
        """Boundary: None identifier raises ValueError (fetch-auth-encoding requires identifier)"""
        auth = AuthConfig(type="basic_email_token", email=None, raw_api_key="token")
        with pytest.raises(ValueError):
            format_auth_header_value(auth, "token")

    def test_special_characters_in_credentials(self):
        """Boundary: special characters preserved in base64 encoding"""
        auth = AuthConfig(type="basic", email="user+tag@email.com", raw_api_key="p@ss:word!")
        result = format_auth_header_value(auth, "p@ss:word!")
        expected = self._encode_basic("user+tag@email.com", "p@ss:word!")
        assert result == expected

    def test_unicode_in_credentials(self):
        """Boundary: unicode characters in credentials"""
        auth = AuthConfig(type="basic", username="用户", raw_api_key="密码")
        result = format_auth_header_value(auth, "密码")
        expected = self._encode_basic("用户", "密码")
        assert result == expected


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
