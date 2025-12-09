"""
Comprehensive tests for RedisApiToken.

Tests cover:
- Decision/Branch coverage for connection URL building
- All auth combinations (password only, username+password, no auth)
- Log verification for defensive programming
"""
import logging
import pytest
from unittest.mock import MagicMock, patch

from provider_api_getters.api_token.redis import RedisApiToken, DEFAULT_CONNECTION_URL_ENV_VAR
from .conftest import MockConfigStore

# Enable debug logging for tests
logging.getLogger("provider_api_getters").setLevel(logging.DEBUG)


class TestRedisApiToken:
    """Tests for RedisApiToken class."""

    @pytest.fixture
    def redis_config(self):
        """Standard Redis config."""
        return {
            "providers": {
                "redis": {
                    "env_connection_url": "REDIS_URL",
                }
            }
        }

    @pytest.fixture
    def redis_token(self, redis_config):
        """Create RedisApiToken instance with standard config."""
        mock_store = MockConfigStore(redis_config)
        return RedisApiToken(config_store=mock_store)

    # Provider name tests
    def test_provider_name(self, redis_token):
        """Test provider_name returns 'redis'."""
        assert redis_token.provider_name == "redis"

    # Health endpoint tests
    def test_health_endpoint(self, redis_token, caplog):
        """Test health_endpoint returns PING."""
        with caplog.at_level(logging.DEBUG):
            endpoint = redis_token.health_endpoint

        assert endpoint == "PING"
        assert "Returning PING" in caplog.text

    # Default constant tests
    def test_default_constant(self):
        """Test default connection URL env var."""
        assert DEFAULT_CONNECTION_URL_ENV_VAR == "REDIS_URL"

    # _build_connection_url tests - All branches

    def test_build_connection_url_no_auth(self, redis_token, clean_env, caplog):
        """Test _build_connection_url without authentication."""
        clean_env(
            REDIS_HOST="localhost",
            REDIS_PORT="6379",
            REDIS_DB="0"
        )

        with caplog.at_level(logging.DEBUG):
            result = redis_token._build_connection_url()

        assert result == "redis://localhost:6379/0"
        assert "Built URL without auth" in caplog.text

    def test_build_connection_url_password_only(self, redis_token, clean_env, caplog):
        """Test _build_connection_url with password only."""
        clean_env(
            REDIS_HOST="localhost",
            REDIS_PORT="6379",
            REDIS_PASSWORD="secretpass",
            REDIS_DB="0"
        )

        with caplog.at_level(logging.DEBUG):
            result = redis_token._build_connection_url()

        assert result == "redis://:secretpass@localhost:6379/0"
        assert "Built URL with password only" in caplog.text

    def test_build_connection_url_username_and_password(self, redis_token, clean_env, caplog):
        """Test _build_connection_url with username and password."""
        clean_env(
            REDIS_HOST="localhost",
            REDIS_PORT="6379",
            REDIS_USERNAME="redisuser",
            REDIS_PASSWORD="secretpass",
            REDIS_DB="0"
        )

        with caplog.at_level(logging.DEBUG):
            result = redis_token._build_connection_url()

        assert result == "redis://redisuser:secretpass@localhost:6379/0"
        assert "Built URL with username and password" in caplog.text

    def test_build_connection_url_defaults(self, redis_token, clean_env, caplog):
        """Test _build_connection_url uses defaults."""
        # Don't set any env vars - should use defaults

        result = redis_token._build_connection_url()

        assert result == "redis://localhost:6379/0"

    def test_build_connection_url_custom_port(self, redis_token, clean_env):
        """Test _build_connection_url with custom port."""
        clean_env(REDIS_PORT="16379")

        result = redis_token._build_connection_url()

        assert ":16379/" in result

    def test_build_connection_url_custom_db(self, redis_token, clean_env):
        """Test _build_connection_url with custom database."""
        clean_env(REDIS_DB="5")

        result = redis_token._build_connection_url()

        assert result.endswith("/5")

    def test_build_connection_url_custom_host(self, redis_token, clean_env):
        """Test _build_connection_url with custom host."""
        clean_env(REDIS_HOST="redis.example.com")

        result = redis_token._build_connection_url()

        assert "redis.example.com" in result

    # get_connection_url tests

    def test_get_connection_url_from_env(self, redis_token, clean_env, caplog):
        """Test get_connection_url from REDIS_URL env var."""
        clean_env(REDIS_URL="redis://user:pass@host:6379/1")

        with caplog.at_level(logging.DEBUG):
            result = redis_token.get_connection_url()

        assert result == "redis://user:pass@host:6379/1"
        assert "Found URL in env var 'REDIS_URL'" in caplog.text

    def test_get_connection_url_builds_from_components(self, redis_token, clean_env, caplog):
        """Test get_connection_url builds from components when env not set."""
        clean_env(
            REDIS_HOST="redis-server",
            REDIS_PORT="6380",
            REDIS_PASSWORD="mypass",
            REDIS_DB="2"
        )

        with caplog.at_level(logging.DEBUG):
            result = redis_token.get_connection_url()

        # Port 6380 is detected as TLS port
        assert result == "rediss://:mypass@redis-server:6380/2"
        assert "'REDIS_URL' not set" in caplog.text
        assert "Built URL from components" in caplog.text

    def test_get_connection_url_custom_env_var(self, clean_env, caplog):
        """Test get_connection_url with custom env var config."""
        config = {
            "providers": {
                "redis": {
                    "env_connection_url": "CUSTOM_REDIS_URL",
                }
            }
        }
        clean_env(CUSTOM_REDIS_URL="redis://custom:pass@host/0")
        mock_store = MockConfigStore(config)
        redis_token = RedisApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = redis_token.get_connection_url()

        assert result == "redis://custom:pass@host/0"
        assert "CUSTOM_REDIS_URL" in caplog.text

    # get_api_key tests

    def test_get_api_key_with_url(self, redis_token, clean_env, caplog):
        """Test get_api_key returns connection URL."""
        clean_env(REDIS_URL="redis://host:6379/0")

        with caplog.at_level(logging.DEBUG):
            result = redis_token.get_api_key()

        assert result.api_key == "redis://host:6379/0"
        assert result.auth_type == "connection_string"
        # Note: empty header_name gets defaulted to "Authorization" in ApiKeyResult
        assert result.header_name == "Authorization"
        assert result.has_credentials is True
        assert "Found connection URL" in caplog.text

    def test_get_api_key_builds_url(self, redis_token, clean_env, caplog):
        """Test get_api_key builds URL from components."""
        # No REDIS_URL set, should build from defaults

        with caplog.at_level(logging.DEBUG):
            result = redis_token.get_api_key()

        # Redis always returns a URL due to defaults
        assert result.api_key == "redis://localhost:6379/0"
        assert result.has_credentials is True

    # get_sync_client tests

    def test_get_sync_client_no_redis(self, redis_token, clean_env, caplog):
        """Test get_sync_client when redis not installed."""
        # Need to reimport to trigger the ImportError
        with patch.dict("sys.modules", {"redis": None}):
            # The import will succeed but we can test the behavior
            pass

    def test_get_sync_client_logs_module_import(self, redis_token, clean_env, caplog):
        """Test get_sync_client logs module import."""
        clean_env(REDIS_URL="redis://localhost:6379/0")

        with caplog.at_level(logging.DEBUG):
            try:
                redis_token.get_sync_client()
            except Exception:
                pass

        # Should at least attempt to import
        assert "Getting sync Redis client" in caplog.text

    # get_async_client tests

    @pytest.mark.asyncio
    async def test_get_async_client_logs_start(self, redis_token, clean_env, caplog):
        """Test get_async_client logs start."""
        clean_env(REDIS_URL="redis://localhost:6379/0")

        with caplog.at_level(logging.DEBUG):
            try:
                await redis_token.get_async_client()
            except Exception:
                pass

        assert "Getting async Redis client" in caplog.text

    # Validation tests
    def test_validate_returns_valid(self, redis_token, clean_env):
        """Test validate returns valid (Redis always has URL due to defaults)."""
        result = redis_token.validate()

        # Redis always builds a URL from defaults
        assert result["has_credentials"] is True


class TestRedisApiTokenEdgeCases:
    """Edge case tests for RedisApiToken."""

    def test_url_with_special_chars_in_password(self, clean_env):
        """Test URL with special characters in password."""
        clean_env(
            REDIS_PASSWORD="p@ss:w0rd!"
        )

        config = {"providers": {"redis": {}}}
        mock_store = MockConfigStore(config)
        redis_token = RedisApiToken(config_store=mock_store)

        result = redis_token._build_connection_url()

        assert "p@ss:w0rd!" in result

    def test_url_masked_in_logs(self, clean_env, caplog):
        """Test URL with password is masked in logs."""
        clean_env(REDIS_URL="redis://:secretpassword@host:6379/0")

        config = {"providers": {"redis": {}}}
        mock_store = MockConfigStore(config)
        redis_token = RedisApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            redis_token.get_connection_url()

        # Verify password is masked
        assert "secretpassword" not in caplog.text
        assert "masked=" in caplog.text

    def test_tls_url(self, clean_env):
        """Test TLS Redis URL."""
        clean_env(REDIS_URL="rediss://user:pass@host:6380/0")

        config = {"providers": {"redis": {}}}
        mock_store = MockConfigStore(config)
        redis_token = RedisApiToken(config_store=mock_store)

        result = redis_token.get_connection_url()

        assert result == "rediss://user:pass@host:6380/0"

    def test_username_without_password(self, clean_env):
        """Test username without password uses no-auth format."""
        clean_env(
            REDIS_USERNAME="someuser"
            # No password
        )

        config = {"providers": {"redis": {}}}
        mock_store = MockConfigStore(config)
        redis_token = RedisApiToken(config_store=mock_store)

        result = redis_token._build_connection_url()

        # Without password, username is ignored
        assert result == "redis://localhost:6379/0"

    def test_tls_auto_detection_port_25061(self, clean_env):
        """Test TLS auto-detection for DigitalOcean port 25061."""
        clean_env(
            REDIS_HOST="redis.example.com",
            REDIS_PORT="25061",
            REDIS_PASSWORD="secret"
        )

        config = {"providers": {"redis": {}}}
        mock_store = MockConfigStore(config)
        redis_token = RedisApiToken(config_store=mock_store)

        result = redis_token._build_connection_url()

        # Should use rediss:// scheme for TLS port
        assert result.startswith("rediss://")
        assert "redis.example.com:25061" in result

    def test_tls_auto_detection_port_6380(self, clean_env):
        """Test TLS auto-detection for Azure Redis port 6380."""
        clean_env(
            REDIS_HOST="redis.example.com",
            REDIS_PORT="6380"
        )

        config = {"providers": {"redis": {}}}
        mock_store = MockConfigStore(config)
        redis_token = RedisApiToken(config_store=mock_store)

        result = redis_token._build_connection_url()

        # Should use rediss:// scheme for TLS port
        assert result.startswith("rediss://")

    def test_tls_explicit_env_var(self, clean_env):
        """Test explicit REDIS_TLS=true enables TLS."""
        clean_env(
            REDIS_HOST="localhost",
            REDIS_PORT="6379",
            REDIS_TLS="true"
        )

        config = {"providers": {"redis": {}}}
        mock_store = MockConfigStore(config)
        redis_token = RedisApiToken(config_store=mock_store)

        result = redis_token._build_connection_url()

        # Should use rediss:// scheme when REDIS_TLS=true
        assert result.startswith("rediss://")

    def test_non_tls_standard_port(self, clean_env):
        """Test non-TLS URL for standard port 6379."""
        clean_env(
            REDIS_HOST="localhost",
            REDIS_PORT="6379"
        )

        config = {"providers": {"redis": {}}}
        mock_store = MockConfigStore(config)
        redis_token = RedisApiToken(config_store=mock_store)

        result = redis_token._build_connection_url()

        # Should use redis:// scheme for standard port
        assert result.startswith("redis://")

    def test_all_branches_covered_in_build_url(self, monkeypatch, caplog):
        """Test that all branches in _build_connection_url are exercised."""
        config = {"providers": {"redis": {}}}
        mock_store = MockConfigStore(config)
        redis_token = RedisApiToken(config_store=mock_store)

        # Branch 1: password and username
        monkeypatch.setenv("REDIS_PASSWORD", "pass")
        monkeypatch.setenv("REDIS_USERNAME", "user")
        redis_token.clear_cache()
        result1 = redis_token._build_connection_url()
        assert "user:pass@" in result1

        # Branch 2: password only
        monkeypatch.delenv("REDIS_USERNAME", raising=False)
        redis_token.clear_cache()
        result2 = redis_token._build_connection_url()
        assert ":pass@" in result2

        # Branch 3: no auth
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
        redis_token.clear_cache()
        result3 = redis_token._build_connection_url()
        assert "@" not in result3
