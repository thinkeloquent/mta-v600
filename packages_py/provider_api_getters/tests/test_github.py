"""
Comprehensive tests for GithubApiToken.

Tests cover:
- Decision/Branch coverage for all control flow
- Fallback environment variable handling
- Log verification for defensive programming
"""
import logging
import pytest

from provider_api_getters.api_token.github import GithubApiToken, GITHUB_FALLBACK_ENV_VARS
from tests.conftest import MockConfigStore

# Enable debug logging for tests
logging.getLogger("provider_api_getters").setLevel(logging.DEBUG)


class TestGithubApiToken:
    """Tests for GithubApiToken class."""

    @pytest.fixture
    def github_token(self, github_config):
        """Create GithubApiToken instance with standard config."""
        mock_store = MockConfigStore(github_config)
        return GithubApiToken(config_store=mock_store)

    # Provider name tests
    def test_provider_name(self, github_token):
        """Test provider_name returns 'github'."""
        assert github_token.provider_name == "github"

    # Health endpoint tests
    def test_health_endpoint(self, github_token, caplog):
        """Test health_endpoint returns /user."""
        with caplog.at_level(logging.DEBUG):
            endpoint = github_token.health_endpoint

        assert endpoint == "/user"
        assert "Returning /user" in caplog.text

    # Fallback env vars tests
    def test_fallback_env_vars_constant(self):
        """Test fallback env vars are defined correctly."""
        assert GITHUB_FALLBACK_ENV_VARS == (
            "GITHUB_TOKEN",
            "GH_TOKEN",
            "GITHUB_ACCESS_TOKEN",
            "GITHUB_PAT",
        )

    def test_get_fallback_env_vars(self, github_token):
        """Test _get_fallback_env_vars returns correct tuple."""
        result = github_token._get_fallback_env_vars()
        assert result == GITHUB_FALLBACK_ENV_VARS

    # get_api_key with configured env var tests

    def test_get_api_key_with_configured_var(self, github_token, clean_env, caplog):
        """Test get_api_key uses configured GITHUB_TOKEN first."""
        clean_env(GITHUB_TOKEN="configured_token_123")

        with caplog.at_level(logging.DEBUG):
            result = github_token.get_api_key()

        assert result.api_key == "configured_token_123"
        assert result.auth_type == "bearer"
        assert result.header_name == "Authorization"
        assert result.has_credentials is True
        assert "has_credentials=True" in caplog.text

    # Fallback env var priority tests

    def test_get_api_key_fallback_gh_token(self, github_token, clean_env, caplog):
        """Test get_api_key falls back to GH_TOKEN."""
        clean_env(GH_TOKEN="gh_token_value")

        with caplog.at_level(logging.DEBUG):
            result = github_token.get_api_key()

        assert result.api_key == "gh_token_value"
        assert "Found key in fallback env var 'GH_TOKEN'" in caplog.text

    def test_get_api_key_fallback_access_token(self, github_token, clean_env, caplog):
        """Test get_api_key falls back to GITHUB_ACCESS_TOKEN."""
        clean_env(GITHUB_ACCESS_TOKEN="access_token_value")

        with caplog.at_level(logging.DEBUG):
            result = github_token.get_api_key()

        assert result.api_key == "access_token_value"
        assert "Found key in fallback env var 'GITHUB_ACCESS_TOKEN'" in caplog.text

    def test_get_api_key_fallback_pat(self, github_token, clean_env, caplog):
        """Test get_api_key falls back to GITHUB_PAT."""
        clean_env(GITHUB_PAT="pat_token_value")

        with caplog.at_level(logging.DEBUG):
            result = github_token.get_api_key()

        assert result.api_key == "pat_token_value"
        assert "Found key in fallback env var 'GITHUB_PAT'" in caplog.text

    def test_get_api_key_priority_order(self, clean_env, caplog):
        """Test fallback priority order is respected."""
        # Set all fallback vars
        clean_env(
            GITHUB_TOKEN="token1",
            GH_TOKEN="token2",
            GITHUB_ACCESS_TOKEN="token3",
            GITHUB_PAT="token4",
        )

        config = {"providers": {"github": {"env_api_key": "GITHUB_TOKEN"}}}
        mock_store = MockConfigStore(config)
        github_token = GithubApiToken(config_store=mock_store)

        result = github_token.get_api_key()

        # Configured var (GITHUB_TOKEN) should be used first
        assert result.api_key == "token1"

    def test_get_api_key_skips_configured_if_not_set(self, clean_env, caplog):
        """Test that configured var is skipped if not set."""
        # Don't set GITHUB_TOKEN, but set GH_TOKEN
        clean_env(GH_TOKEN="gh_fallback")

        config = {"providers": {"github": {"env_api_key": "GITHUB_TOKEN"}}}
        mock_store = MockConfigStore(config)
        github_token = GithubApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = github_token.get_api_key()

        assert result.api_key == "gh_fallback"
        assert "'GITHUB_TOKEN' is not set" in caplog.text
        assert "Found key in fallback env var 'GH_TOKEN'" in caplog.text

    # No token found tests

    def test_get_api_key_no_token_found(self, github_token, clean_env, caplog):
        """Test get_api_key when no token is found."""
        with caplog.at_level(logging.WARNING):
            result = github_token.get_api_key()

        assert result.api_key is None
        assert result.has_credentials is False
        assert "No API key found" in caplog.text
        assert "GITHUB_FALLBACK_ENV_VARS" in caplog.text or "environment variables is set" in caplog.text

    # Log verification tests

    def test_get_api_key_logs_all_fallback_checks(self, github_token, clean_env, caplog):
        """Test that all fallback checks are logged."""
        with caplog.at_level(logging.DEBUG):
            github_token.get_api_key()

        # Verify all fallback vars were checked
        for env_var in GITHUB_FALLBACK_ENV_VARS:
            assert env_var in caplog.text

    def test_get_api_key_logs_masked_token(self, github_token, clean_env, caplog):
        """Test that token is properly masked in logs."""
        clean_env(GITHUB_TOKEN="ghp_supersecrettoken123")

        with caplog.at_level(logging.DEBUG):
            github_token.get_api_key()

        # Verify token is masked
        assert "ghp_supersecrettoken123" not in caplog.text
        assert "ghp_" in caplog.text  # First 4 chars
        assert "****" in caplog.text  # Masked portion

    # _lookup_with_fallbacks tests

    def test_lookup_with_fallbacks_returns_source(self, github_token, clean_env, caplog):
        """Test _lookup_with_fallbacks returns source env var name."""
        clean_env(GH_TOKEN="test_token")

        with caplog.at_level(logging.DEBUG):
            api_key, source_var = github_token._lookup_with_fallbacks()

        assert api_key == "test_token"
        assert source_var == "GH_TOKEN"

    def test_lookup_with_fallbacks_returns_none_tuple(self, github_token, clean_env, caplog):
        """Test _lookup_with_fallbacks returns (None, None) when not found."""
        with caplog.at_level(logging.DEBUG):
            api_key, source_var = github_token._lookup_with_fallbacks()

        assert api_key is None
        assert source_var is None
        assert "No API key found in any env var" in caplog.text

    # Validation tests

    def test_validate_with_valid_config(self, github_token, clean_env):
        """Test validate with valid configuration."""
        clean_env(GITHUB_TOKEN="test_token")

        result = github_token.validate()

        assert result["valid"] is True
        assert result["has_credentials"] is True
        assert result["has_base_url"] is True

    def test_validate_without_credentials(self, github_token, clean_env):
        """Test validate detects missing credentials."""
        result = github_token.validate()

        assert result["valid"] is False
        assert "No API credentials available" in result["issues"]


class TestGithubApiTokenEdgeCases:
    """Edge case and boundary tests for GithubApiToken."""

    def test_token_with_ghp_prefix(self, clean_env):
        """Test handling of token with ghp_ prefix (fine-grained token)."""
        clean_env(GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx")

        config = {"providers": {"github": {"env_api_key": "GITHUB_TOKEN"}}}
        mock_store = MockConfigStore(config)
        github_token = GithubApiToken(config_store=mock_store)

        result = github_token.get_api_key()

        assert result.api_key == "ghp_xxxxxxxxxxxxxxxxxxxx"

    def test_token_with_gho_prefix(self, clean_env):
        """Test handling of token with gho_ prefix (OAuth token)."""
        clean_env(GITHUB_TOKEN="gho_xxxxxxxxxxxxxxxxxxxx")

        config = {"providers": {"github": {"env_api_key": "GITHUB_TOKEN"}}}
        mock_store = MockConfigStore(config)
        github_token = GithubApiToken(config_store=mock_store)

        result = github_token.get_api_key()

        assert result.api_key == "gho_xxxxxxxxxxxxxxxxxxxx"

    def test_empty_configured_var_uses_fallback(self, clean_env, caplog):
        """Test empty configured var triggers fallback."""
        clean_env(GITHUB_TOKEN="", GH_TOKEN="fallback_value")

        config = {"providers": {"github": {"env_api_key": "GITHUB_TOKEN"}}}
        mock_store = MockConfigStore(config)
        github_token = GithubApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = github_token.get_api_key()

        # Empty string is falsy, so should fall back
        assert result.api_key == "fallback_value"

    def test_custom_env_var_config(self, clean_env, caplog):
        """Test custom env_api_key configuration."""
        clean_env(MY_CUSTOM_GH_TOKEN="custom_value")

        config = {"providers": {"github": {"env_api_key": "MY_CUSTOM_GH_TOKEN"}}}
        mock_store = MockConfigStore(config)
        github_token = GithubApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = github_token.get_api_key()

        assert result.api_key == "custom_value"
        assert "MY_CUSTOM_GH_TOKEN" in caplog.text

    def test_multiple_sequential_calls(self, clean_env):
        """Test multiple sequential get_api_key calls."""
        clean_env(GITHUB_TOKEN="token123")

        config = {"providers": {"github": {"env_api_key": "GITHUB_TOKEN"}}}
        mock_store = MockConfigStore(config)
        github_token = GithubApiToken(config_store=mock_store)

        results = [github_token.get_api_key() for _ in range(5)]

        for result in results:
            assert result.api_key == "token123"

    def test_fallback_iteration_count(self, clean_env, caplog):
        """Test all fallback iterations are logged."""
        with caplog.at_level(logging.DEBUG):
            config = {"providers": {"github": {"env_api_key": "GITHUB_TOKEN"}}}
            mock_store = MockConfigStore(config)
            github_token = GithubApiToken(config_store=mock_store)
            github_token.get_api_key()

        # Verify iteration logging
        assert "[1/" in caplog.text
        assert "[2/" in caplog.text
        assert "[3/" in caplog.text
        assert "[4/" in caplog.text
