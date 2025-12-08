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
    def test_health_endpoint(self, jira_token, caplog):
        """Test health_endpoint returns /rest/api/2/myself."""
        with caplog.at_level(logging.DEBUG):
            endpoint = jira_token.health_endpoint

        assert endpoint == "/rest/api/2/myself"
        assert "Returning /rest/api/2/myself" in caplog.text

    # Default env var constants
    def test_default_constants(self):
        """Test default env var constants are correct."""
        assert DEFAULT_EMAIL_ENV_VAR == "JIRA_EMAIL"
        assert DEFAULT_BASE_URL_ENV_VAR == "JIRA_BASE_URL"

    # _get_email_env_var_name tests
    def test_get_email_env_var_name_default(self, jira_token, caplog):
        """Test _get_email_env_var_name uses default."""
        with caplog.at_level(logging.DEBUG):
            result = jira_token._get_email_env_var_name()

        assert result == "JIRA_EMAIL"
        assert "from_config=" in caplog.text

    def test_get_email_env_var_name_from_config(self, caplog):
        """Test _get_email_env_var_name uses config value."""
        config = {
            "providers": {
                "jira": {
                    "env_api_key": "JIRA_API_TOKEN",
                    "env_email": "CUSTOM_JIRA_EMAIL",
                }
            }
        }
        mock_store = MockConfigStore(config)
        jira_token = JiraApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = jira_token._get_email_env_var_name()

        assert result == "CUSTOM_JIRA_EMAIL"
        assert "from_config=True" in caplog.text

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

    # _encode_basic_auth tests
    def test_encode_basic_auth_valid(self, jira_token, caplog):
        """Test _encode_basic_auth with valid inputs."""
        with caplog.at_level(logging.DEBUG):
            result = jira_token._encode_basic_auth("user@test.com", "api_token")

        # Verify encoding
        expected = base64.b64encode(b"user@test.com:api_token").decode("utf-8")
        assert result == f"Basic {expected}"
        assert "Encoding credentials" in caplog.text
        assert f"length={len(expected)}" in caplog.text

    def test_encode_basic_auth_empty_email(self, jira_token, caplog):
        """Test _encode_basic_auth with empty email raises error."""
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError) as exc_info:
                jira_token._encode_basic_auth("", "token")

        assert "Both email and token are required" in str(exc_info.value)
        assert "email_empty=True" in caplog.text

    def test_encode_basic_auth_empty_token(self, jira_token, caplog):
        """Test _encode_basic_auth with empty token raises error."""
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError) as exc_info:
                jira_token._encode_basic_auth("user@test.com", "")

        assert "Both email and token are required" in str(exc_info.value)
        assert "token_empty=True" in caplog.text

    def test_encode_basic_auth_both_empty(self, jira_token, caplog):
        """Test _encode_basic_auth with both empty raises error."""
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError):
                jira_token._encode_basic_auth("", "")

        assert "email_empty=True, token_empty=True" in caplog.text

    # get_api_key branch tests - CRITICAL: Tests all 4 branches

    def test_get_api_key_both_token_and_email(self, jira_token, clean_env, caplog):
        """Branch 1: Both token and email present - success path."""
        clean_env(JIRA_API_TOKEN="jira_api_token_123", JIRA_EMAIL="user@company.com")

        with caplog.at_level(logging.DEBUG):
            result = jira_token.get_api_key()

        assert result.api_key is not None
        assert result.api_key.startswith("Basic ")
        assert result.auth_type == "basic"
        assert result.header_name == "Authorization"
        assert result.username == "user@company.com"
        assert result.has_credentials is True

        # Verify logs
        assert "has_token=True, has_email=True" in caplog.text
        assert "Both email and token found" in caplog.text
        assert "Successfully created Basic Auth result" in caplog.text

    def test_get_api_key_token_only(self, jira_token, clean_env, caplog):
        """Branch 2: Token present but email missing."""
        clean_env(JIRA_API_TOKEN="jira_api_token_123")
        # JIRA_EMAIL not set

        with caplog.at_level(logging.WARNING):
            result = jira_token.get_api_key()

        assert result.api_key is None
        assert result.auth_type == "basic"
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
        assert result.auth_type == "basic"
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
        assert result.auth_type == "basic"
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

        config = {"providers": {"jira": {"env_api_key": "JIRA_API_TOKEN"}}}
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
