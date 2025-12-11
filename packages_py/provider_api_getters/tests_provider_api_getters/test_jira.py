"""
Comprehensive tests for JiraApiToken.

Tests cover:
- Decision/Branch coverage for all control flow (4 branches in get_api_key)
- Basic Auth encoding
- Log verification for defensive programming
"""
import base64
import logging
import pytest

from provider_api_getters.api_token.jira import JiraApiToken, DEFAULT_EMAIL_ENV_VAR, DEFAULT_BASE_URL_ENV_VAR
from .conftest import MockConfigStore

# Enable debug logging for tests
logging.getLogger("provider_api_getters").setLevel(logging.DEBUG)


class TestJiraApiToken:
    """Tests for JiraApiToken class."""

    @pytest.fixture
    def jira_token(self, jira_config):
        """Create JiraApiToken instance with standard config."""
        mock_store = MockConfigStore(jira_config)
        return JiraApiToken(config_store=mock_store)

    # Provider name tests
    def test_provider_name(self, jira_token):
        """Test provider_name returns 'jira'."""
        assert jira_token.provider_name == "jira"

    # Health endpoint tests
    def test_health_endpoint_from_config(self, jira_token, caplog):
        """Test health_endpoint returns value from config."""
        with caplog.at_level(logging.DEBUG):
            endpoint = jira_token.health_endpoint

        # Value comes from jira_config fixture which sets health_endpoint: "/myself"
        assert endpoint == "/myself"

    def test_health_endpoint_custom_from_config(self, clean_env, caplog):
        """Test health_endpoint returns custom value from config."""
        config = {
            "providers": {
                "jira": {
                    "env_api_key": "JIRA_API_TOKEN",
                    "health_endpoint": "/user/current",
                }
            }
        }
        mock_store = MockConfigStore(config)
        jira_token = JiraApiToken(config_store=mock_store)

        endpoint = jira_token.health_endpoint
        assert endpoint == "/user/current"

    def test_health_endpoint_default_when_not_in_config(self, clean_env):
        """Test health_endpoint returns default when not in config."""
        config = {
            "providers": {
                "jira": {
                    "env_api_key": "JIRA_API_TOKEN",
                    # No health_endpoint specified
                }
            }
        }
        mock_store = MockConfigStore(config)
        jira_token = JiraApiToken(config_store=mock_store)

        endpoint = jira_token.health_endpoint
        # BaseApiToken returns "/" as default when health_endpoint not specified
        assert endpoint == "/"

    # Default env var constants
    def test_default_constants(self):
        """Test default env var constants are correct."""
        assert DEFAULT_EMAIL_ENV_VAR == "JIRA_EMAIL"
        assert DEFAULT_BASE_URL_ENV_VAR == "JIRA_BASE_URL"

    # _get_email tests
    def test_get_email_found(self, jira_token, clean_env, caplog):
        """Test _get_email when email is set."""
        clean_env(JIRA_EMAIL="user@company.com")

        with caplog.at_level(logging.DEBUG):
            result = jira_token._get_email()

        assert result == "user@company.com"
        assert "Found email in env var 'JIRA_EMAIL'" in caplog.text
        # Verify email is masked
        assert "use***@***" in caplog.text

    def test_get_email_not_found(self, jira_token, clean_env, caplog):
        """Test _get_email when email is not set."""
        with caplog.at_level(logging.DEBUG):
            result = jira_token._get_email()

        assert result is None
        assert "'JIRA_EMAIL' is not set" in caplog.text

    # _encode_auth tests
    def test_encode_auth_basic_type(self, jira_token, caplog):
        """Test _encode_auth with basic auth type."""
        with caplog.at_level(logging.DEBUG):
            result = jira_token._encode_auth("user@test.com", "api_token", "basic_email_token")

        # Verify encoding
        expected = base64.b64encode(b"user@test.com:api_token").decode("utf-8")
        assert result == f"Basic {expected}"
        assert "Encoding credentials" in caplog.text

    def test_encode_auth_bearer_type(self, jira_token, caplog):
        """Test _encode_auth with bearer auth type."""
        with caplog.at_level(logging.DEBUG):
            result = jira_token._encode_auth("user@test.com", "api_token", "bearer_email_token")

        # Verify encoding - Bearer with base64-encoded credentials
        expected = base64.b64encode(b"user@test.com:api_token").decode("utf-8")
        assert result == f"Bearer {expected}"
        assert "Encoding credentials" in caplog.text

    def test_encode_auth_empty_email_raises(self, jira_token, caplog):
        """Test _encode_auth with empty email raises error."""
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError) as exc_info:
                jira_token._encode_auth("", "token", "basic_email_token")

        assert "Both email and token are required" in str(exc_info.value)
        assert "email_empty=True" in caplog.text

    def test_encode_auth_empty_token_raises(self, jira_token, caplog):
        """Test _encode_auth with empty token raises error."""
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError) as exc_info:
                jira_token._encode_auth("user@test.com", "", "basic_email_token")

        assert "Both email and token are required" in str(exc_info.value)
        assert "token_empty=True" in caplog.text

    def test_encode_auth_both_empty_raises(self, jira_token, caplog):
        """Test _encode_auth with both empty raises error."""
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError):
                jira_token._encode_auth("", "", "basic_email_token")

        assert "email_empty=True, token_empty=True" in caplog.text

    # get_api_key branch tests - CRITICAL: Tests all 4 branches

    def test_get_api_key_both_token_and_email(self, jira_token, clean_env, caplog):
        """Branch 1: Both token and email present - success path."""
        clean_env(JIRA_API_TOKEN="jira_api_token_123", JIRA_EMAIL="user@company.com")

        with caplog.at_level(logging.DEBUG):
            result = jira_token.get_api_key()

        assert result.api_key is not None
        assert result.api_key.startswith("Basic ")
        assert result.auth_type == "basic_email_token"
        assert result.header_name == "Authorization"
        assert result.username == "user@company.com"
        assert result.has_credentials is True

        # Verify logs
        assert "has_token=True, has_email=True" in caplog.text
        assert "Both email and token found" in caplog.text
        assert "Successfully created auth result" in caplog.text

    def test_get_api_key_token_only(self, jira_token, clean_env, caplog):
        """Branch 2: Token present but email missing."""
        clean_env(JIRA_API_TOKEN="jira_api_token_123")
        # JIRA_EMAIL not set

        with caplog.at_level(logging.WARNING):
            result = jira_token.get_api_key()

        assert result.api_key is None
        assert result.auth_type == "basic_email_token"
        assert result.username is None
        assert result.has_credentials is False

        # Verify warning log
        assert "API token found but email is missing" in caplog.text
        assert "Set JIRA_EMAIL environment variable" in caplog.text

    def test_get_api_key_email_only(self, jira_token, clean_env, caplog):
        """Branch 3: Email present but token missing."""
        clean_env(JIRA_EMAIL="user@company.com")
        # JIRA_API_TOKEN not set

        with caplog.at_level(logging.WARNING):
            result = jira_token.get_api_key()

        assert result.api_key is None
        assert result.auth_type == "basic_email_token"
        assert result.username == "user@company.com"
        assert result.has_credentials is False

        # Verify warning log
        assert "Email found but API token is missing" in caplog.text
        assert "Set JIRA_API_TOKEN environment variable" in caplog.text

    def test_get_api_key_neither(self, jira_token, clean_env, caplog):
        """Branch 4: Neither token nor email present."""
        # Both not set

        with caplog.at_level(logging.WARNING):
            result = jira_token.get_api_key()

        assert result.api_key is None
        assert result.auth_type == "basic_email_token"
        assert result.username is None
        assert result.has_credentials is False

        # Verify warning log
        assert "Neither email nor token found" in caplog.text
        assert "Set both JIRA_EMAIL and JIRA_API_TOKEN environment variables" in caplog.text

    def test_get_api_key_credential_state_logging(self, jira_token, clean_env, caplog):
        """Test credential state is logged correctly."""
        clean_env(JIRA_API_TOKEN="token", JIRA_EMAIL="email@test.com")

        with caplog.at_level(logging.DEBUG):
            jira_token.get_api_key()

        assert "Credential state - has_token=True, has_email=True" in caplog.text

    # get_base_url tests
    def test_get_base_url_from_env(self, jira_token, clean_env, caplog):
        """Test get_base_url from environment variable."""
        clean_env(JIRA_BASE_URL="https://company.atlassian.net")

        with caplog.at_level(logging.DEBUG):
            result = jira_token.get_base_url()

        assert result == "https://company.atlassian.net"
        assert "Found base URL from env var" in caplog.text

    def test_get_base_url_not_configured(self, jira_token, clean_env, caplog):
        """Test get_base_url when not configured."""
        with caplog.at_level(logging.WARNING):
            result = jira_token.get_base_url()

        assert result is None
        assert "No base URL configured" in caplog.text
        assert "Set JIRA_BASE_URL environment variable" in caplog.text

    def test_get_base_url_from_config(self, clean_env, caplog):
        """Test get_base_url from config takes precedence."""
        config = {
            "providers": {
                "jira": {
                    "base_url": "https://config.atlassian.net",
                    "env_api_key": "JIRA_API_TOKEN",
                }
            }
        }
        mock_store = MockConfigStore(config)
        jira_token = JiraApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = jira_token.get_base_url()

        assert result == "https://config.atlassian.net"
        assert "Found base URL from config" in caplog.text

    # Validation tests
    def test_validate_fully_configured(self, clean_env):
        """Test validate with full configuration."""
        clean_env(
            JIRA_API_TOKEN="token",
            JIRA_EMAIL="user@test.com",
            JIRA_BASE_URL="https://company.atlassian.net"
        )

        config = {"providers": {"jira": {"env_api_key": "JIRA_API_TOKEN"}}}
        mock_store = MockConfigStore(config)
        jira_token = JiraApiToken(config_store=mock_store)

        result = jira_token.validate()

        assert result["valid"] is True
        assert result["has_credentials"] is True
        assert result["has_base_url"] is True


class TestJiraApiTokenEdgeCases:
    """Edge case and boundary tests for JiraApiToken."""

    def test_email_with_special_chars(self, clean_env):
        """Test email with special characters."""
        clean_env(
            JIRA_API_TOKEN="token",
            JIRA_EMAIL="user+tag@company.com"
        )

        config = {"providers": {"jira": {"env_api_key": "JIRA_API_TOKEN"}}}
        mock_store = MockConfigStore(config)
        jira_token = JiraApiToken(config_store=mock_store)

        result = jira_token.get_api_key()

        assert result.has_credentials is True
        assert result.username == "user+tag@company.com"

    def test_token_with_special_chars(self, clean_env):
        """Test token with special characters in Basic Auth."""
        clean_env(
            JIRA_API_TOKEN="token:with:colons",
            JIRA_EMAIL="user@test.com"
        )

        config = {"providers": {"jira": {"env_api_key": "JIRA_API_TOKEN", "api_auth_type": "basic_email_token"}}}
        mock_store = MockConfigStore(config)
        jira_token = JiraApiToken(config_store=mock_store)

        result = jira_token.get_api_key()

        # Verify the encoding handles colons correctly
        assert result.has_credentials is True
        # Decode and verify
        decoded = base64.b64decode(result.api_key.replace("Basic ", "")).decode("utf-8")
        assert decoded == "user@test.com:token:with:colons"

    def test_unicode_email(self, clean_env):
        """Test unicode characters in email."""
        clean_env(
            JIRA_API_TOKEN="token",
            JIRA_EMAIL="üser@company.com"
        )

        config = {"providers": {"jira": {"env_api_key": "JIRA_API_TOKEN"}}}
        mock_store = MockConfigStore(config)
        jira_token = JiraApiToken(config_store=mock_store)

        result = jira_token.get_api_key()

        assert result.has_credentials is True

    def test_very_long_credentials(self, clean_env):
        """Test very long credentials."""
        long_token = "a" * 1000
        long_email = "x" * 100 + "@" + "y" * 100 + ".com"

        clean_env(JIRA_API_TOKEN=long_token, JIRA_EMAIL=long_email)

        config = {"providers": {"jira": {"env_api_key": "JIRA_API_TOKEN"}}}
        mock_store = MockConfigStore(config)
        jira_token = JiraApiToken(config_store=mock_store)

        result = jira_token.get_api_key()

        assert result.has_credentials is True
        assert result.username == long_email

    def test_masked_email_in_logs(self, clean_env, caplog):
        """Test that email is masked in success log."""
        clean_env(
            JIRA_API_TOKEN="token",
            JIRA_EMAIL="user@company.com"
        )

        config = {"providers": {"jira": {"env_api_key": "JIRA_API_TOKEN"}}}
        mock_store = MockConfigStore(config)
        jira_token = JiraApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            jira_token.get_api_key()

        # Verify email is masked
        assert "user@company.com" not in caplog.text
        assert "use***@***" in caplog.text


class TestJiraApiTokenAuthTypes:
    """Comprehensive auth type encoding tests."""

    # Basic auth type family tests
    class TestBasicAuthTypes:
        """Tests for Basic auth type family."""

        def test_encode_auth_basic(self, clean_env):
            """Test 'basic' auth type encoding."""
            config = {"providers": {"jira": {"env_api_key": "JIRA_API_TOKEN", "api_auth_type": "basic"}}}
            mock_store = MockConfigStore(config)
            jira_token = JiraApiToken(config_store=mock_store)

            result = jira_token._encode_auth("user@test.com", "api_token", "basic")

            expected = base64.b64encode(b"user@test.com:api_token").decode("utf-8")
            assert result == f"Basic {expected}"

        def test_encode_auth_basic_email_token(self, clean_env):
            """Test 'basic_email_token' auth type encoding."""
            config = {"providers": {"jira": {"env_api_key": "JIRA_API_TOKEN", "api_auth_type": "basic_email_token"}}}
            mock_store = MockConfigStore(config)
            jira_token = JiraApiToken(config_store=mock_store)

            result = jira_token._encode_auth("user@test.com", "api_token", "basic_email_token")

            expected = base64.b64encode(b"user@test.com:api_token").decode("utf-8")
            assert result == f"Basic {expected}"

        def test_encode_auth_basic_email_password(self, clean_env):
            """Test 'basic_email_password' auth type encoding."""
            config = {"providers": {"jira": {"env_api_key": "JIRA_API_TOKEN", "api_auth_type": "basic_email_password"}}}
            mock_store = MockConfigStore(config)
            jira_token = JiraApiToken(config_store=mock_store)

            result = jira_token._encode_auth("user@test.com", "password123", "basic_email_password")

            expected = base64.b64encode(b"user@test.com:password123").decode("utf-8")
            assert result == f"Basic {expected}"

        def test_encode_auth_basic_username_token(self, clean_env):
            """Test 'basic_username_token' auth type encoding."""
            config = {"providers": {"jira": {"env_api_key": "JIRA_API_TOKEN", "api_auth_type": "basic_username_token"}}}
            mock_store = MockConfigStore(config)
            jira_token = JiraApiToken(config_store=mock_store)

            result = jira_token._encode_auth("username", "api_token", "basic_username_token")

            expected = base64.b64encode(b"username:api_token").decode("utf-8")
            assert result == f"Basic {expected}"

        def test_encode_auth_unknown_defaults_to_basic(self, clean_env, caplog):
            """Test unknown auth type defaults to Basic encoding."""
            config = {"providers": {"jira": {"env_api_key": "JIRA_API_TOKEN"}}}
            mock_store = MockConfigStore(config)
            jira_token = JiraApiToken(config_store=mock_store)

            with caplog.at_level(logging.DEBUG):
                result = jira_token._encode_auth("user@test.com", "api_token", "unknown_type")

            expected = base64.b64encode(b"user@test.com:api_token").decode("utf-8")
            assert result == f"Basic {expected}"
            assert "Using Basic encoding for auth_type='unknown_type'" in caplog.text

    # Bearer auth type family tests
    class TestBearerAuthTypes:
        """Tests for Bearer auth type family."""

        def test_encode_auth_bearer(self, clean_env):
            """Test 'bearer' auth type encoding."""
            config = {"providers": {"jira": {"env_api_key": "JIRA_API_TOKEN", "api_auth_type": "bearer"}}}
            mock_store = MockConfigStore(config)
            jira_token = JiraApiToken(config_store=mock_store)

            result = jira_token._encode_auth("user@test.com", "api_token", "bearer")

            expected = base64.b64encode(b"user@test.com:api_token").decode("utf-8")
            assert result == f"Bearer {expected}"

        def test_encode_auth_bearer_email_token(self, clean_env):
            """Test 'bearer_email_token' auth type encoding."""
            config = {"providers": {"jira": {"env_api_key": "JIRA_API_TOKEN", "api_auth_type": "bearer_email_token"}}}
            mock_store = MockConfigStore(config)
            jira_token = JiraApiToken(config_store=mock_store)

            result = jira_token._encode_auth("user@test.com", "api_token", "bearer_email_token")

            expected = base64.b64encode(b"user@test.com:api_token").decode("utf-8")
            assert result == f"Bearer {expected}"

        def test_encode_auth_bearer_email_password(self, clean_env):
            """Test 'bearer_email_password' auth type encoding."""
            config = {"providers": {"jira": {"env_api_key": "JIRA_API_TOKEN", "api_auth_type": "bearer_email_password"}}}
            mock_store = MockConfigStore(config)
            jira_token = JiraApiToken(config_store=mock_store)

            result = jira_token._encode_auth("user@test.com", "password123", "bearer_email_password")

            expected = base64.b64encode(b"user@test.com:password123").decode("utf-8")
            assert result == f"Bearer {expected}"

        def test_encode_auth_bearer_username_token(self, clean_env):
            """Test 'bearer_username_token' auth type encoding."""
            config = {"providers": {"jira": {"env_api_key": "JIRA_API_TOKEN", "api_auth_type": "bearer_username_token"}}}
            mock_store = MockConfigStore(config)
            jira_token = JiraApiToken(config_store=mock_store)

            result = jira_token._encode_auth("username", "api_token", "bearer_username_token")

            expected = base64.b64encode(b"username:api_token").decode("utf-8")
            assert result == f"Bearer {expected}"

        def test_encode_auth_bearer_username_password(self, clean_env):
            """Test 'bearer_username_password' auth type encoding."""
            config = {"providers": {"jira": {"env_api_key": "JIRA_API_TOKEN", "api_auth_type": "bearer_username_password"}}}
            mock_store = MockConfigStore(config)
            jira_token = JiraApiToken(config_store=mock_store)

            result = jira_token._encode_auth("username", "password123", "bearer_username_password")

            expected = base64.b64encode(b"username:password123").decode("utf-8")
            assert result == f"Bearer {expected}"

        def test_encode_auth_bearer_oauth(self, clean_env):
            """Test 'bearer_oauth' auth type encoding."""
            config = {"providers": {"jira": {"env_api_key": "JIRA_API_TOKEN", "api_auth_type": "bearer_oauth"}}}
            mock_store = MockConfigStore(config)
            jira_token = JiraApiToken(config_store=mock_store)

            result = jira_token._encode_auth("client_id", "oauth_token", "bearer_oauth")

            expected = base64.b64encode(b"client_id:oauth_token").decode("utf-8")
            assert result == f"Bearer {expected}"

        def test_encode_auth_bearer_jwt(self, clean_env):
            """Test 'bearer_jwt' auth type encoding."""
            config = {"providers": {"jira": {"env_api_key": "JIRA_API_TOKEN", "api_auth_type": "bearer_jwt"}}}
            mock_store = MockConfigStore(config)
            jira_token = JiraApiToken(config_store=mock_store)

            result = jira_token._encode_auth("issuer", "jwt_token", "bearer_jwt")

            expected = base64.b64encode(b"issuer:jwt_token").decode("utf-8")
            assert result == f"Bearer {expected}"


class TestJiraApiTokenAuthTypeIntegration:
    """Integration tests for auth type through getApiKey flow."""

    def test_get_api_key_produces_basic_header(self, clean_env, caplog):
        """Test getApiKey produces Basic header when config has basic_email_token."""
        clean_env(JIRA_API_TOKEN="secret-token", JIRA_EMAIL="user@test.com")

        config = {
            "providers": {
                "jira": {
                    "env_api_key": "JIRA_API_TOKEN",
                    "env_email": "JIRA_EMAIL",
                    "api_auth_type": "basic_email_token",
                }
            }
        }
        mock_store = MockConfigStore(config)
        jira_token = JiraApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = jira_token.get_api_key()

        assert result.api_key.startswith("Basic ")
        assert result.auth_type == "basic_email_token"
        assert "encoding with auth_type='basic_email_token'" in caplog.text

    def test_get_api_key_produces_bearer_header(self, clean_env, caplog):
        """Test getApiKey produces Bearer header when config has bearer_email_token."""
        clean_env(JIRA_API_TOKEN="secret-token", JIRA_EMAIL="user@test.com")

        config = {
            "providers": {
                "jira": {
                    "env_api_key": "JIRA_API_TOKEN",
                    "env_email": "JIRA_EMAIL",
                    "api_auth_type": "bearer_email_token",
                }
            }
        }
        mock_store = MockConfigStore(config)
        jira_token = JiraApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = jira_token.get_api_key()

        assert result.api_key.startswith("Bearer ")
        assert result.auth_type == "bearer_email_token"
        assert "encoding with auth_type='bearer_email_token'" in caplog.text

    def test_get_api_key_preserves_raw_api_key(self, clean_env):
        """Test getApiKey preserves rawApiKey separate from encoded apiKey."""
        clean_env(JIRA_API_TOKEN="raw-secret-token", JIRA_EMAIL="user@test.com")

        config = {
            "providers": {
                "jira": {
                    "env_api_key": "JIRA_API_TOKEN",
                    "env_email": "JIRA_EMAIL",
                    "api_auth_type": "basic_email_token",
                }
            }
        }
        mock_store = MockConfigStore(config)
        jira_token = JiraApiToken(config_store=mock_store)

        result = jira_token.get_api_key()

        assert result.raw_api_key == "raw-secret-token"
        assert result.api_key != result.raw_api_key
        assert result.api_key.startswith("Basic ")

    def test_get_api_key_returns_auth_type_even_when_missing_credentials(self, clean_env):
        """Test getApiKey returns correct auth type even when credentials missing."""
        # No env vars set

        config = {
            "providers": {
                "jira": {
                    "env_api_key": "JIRA_API_TOKEN",
                    "env_email": "JIRA_EMAIL",
                    "api_auth_type": "bearer_oauth",
                }
            }
        }
        mock_store = MockConfigStore(config)
        jira_token = JiraApiToken(config_store=mock_store)

        result = jira_token.get_api_key()

        assert result.api_key is None
        assert result.auth_type == "bearer_oauth"
