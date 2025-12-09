"""
Comprehensive tests for PostgresApiToken.

Tests cover:
- Decision/Branch coverage for connection URL building
- Fallback from DATABASE_URL to individual components
- Log verification for defensive programming
"""
import logging
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from provider_api_getters.api_token.postgres import PostgresApiToken, DEFAULT_CONNECTION_URL_ENV_VAR
from .conftest import MockConfigStore

# Enable debug logging for tests
logging.getLogger("provider_api_getters").setLevel(logging.DEBUG)


class TestPostgresApiToken:
    """Tests for PostgresApiToken class."""

    @pytest.fixture
    def postgres_config(self):
        """Standard PostgreSQL config."""
        return {
            "providers": {
                "postgres": {
                    "env_connection_url": "DATABASE_URL",
                }
            }
        }

    @pytest.fixture
    def postgres_token(self, postgres_config):
        """Create PostgresApiToken instance with standard config."""
        mock_store = MockConfigStore(postgres_config)
        return PostgresApiToken(config_store=mock_store)

    # Provider name tests
    def test_provider_name(self, postgres_token):
        """Test provider_name returns 'postgres'."""
        assert postgres_token.provider_name == "postgres"

    # Health endpoint tests
    def test_health_endpoint(self, postgres_token, caplog):
        """Test health_endpoint returns SELECT 1."""
        with caplog.at_level(logging.DEBUG):
            endpoint = postgres_token.health_endpoint

        assert endpoint == "SELECT 1"
        assert "Returning SELECT 1" in caplog.text

    # Default constant tests
    def test_default_constant(self):
        """Test default connection URL env var."""
        assert DEFAULT_CONNECTION_URL_ENV_VAR == "DATABASE_URL"

    # _build_connection_url tests - Branch coverage

    def test_build_connection_url_all_components(self, postgres_token, clean_env, caplog):
        """Test _build_connection_url with all components."""
        clean_env(
            POSTGRES_HOST="localhost",
            POSTGRES_PORT="5432",
            POSTGRES_USER="testuser",
            POSTGRES_PASSWORD="testpass",
            POSTGRES_DB="testdb"
        )

        with caplog.at_level(logging.DEBUG):
            result = postgres_token._build_connection_url()

        assert result == "postgresql://testuser:testpass@localhost:5432/testdb"
        assert "Required components present" in caplog.text
        assert "Built URL" in caplog.text

    def test_build_connection_url_without_password(self, postgres_token, clean_env, caplog):
        """Test _build_connection_url without password."""
        clean_env(
            POSTGRES_HOST="localhost",
            POSTGRES_PORT="5432",
            POSTGRES_USER="testuser",
            POSTGRES_DB="testdb"
        )

        with caplog.at_level(logging.DEBUG):
            result = postgres_token._build_connection_url()

        assert result == "postgresql://testuser@localhost:5432/testdb"
        assert "Built URL" in caplog.text

    def test_build_connection_url_default_port(self, postgres_token, clean_env, caplog):
        """Test _build_connection_url uses default port."""
        clean_env(
            POSTGRES_HOST="localhost",
            POSTGRES_USER="testuser",
            POSTGRES_DB="testdb"
        )

        result = postgres_token._build_connection_url()

        assert ":5432/" in result

    def test_build_connection_url_missing_host(self, postgres_token, clean_env, caplog):
        """Test _build_connection_url with missing host."""
        clean_env(
            POSTGRES_USER="testuser",
            POSTGRES_DB="testdb"
        )

        with caplog.at_level(logging.DEBUG):
            result = postgres_token._build_connection_url()

        assert result is None
        assert "Missing required components" in caplog.text
        assert "POSTGRES_HOST" in caplog.text

    def test_build_connection_url_missing_user(self, postgres_token, clean_env, caplog):
        """Test _build_connection_url with missing user."""
        clean_env(
            POSTGRES_HOST="localhost",
            POSTGRES_DB="testdb"
        )

        with caplog.at_level(logging.DEBUG):
            result = postgres_token._build_connection_url()

        assert result is None
        assert "POSTGRES_USER" in caplog.text

    def test_build_connection_url_missing_db(self, postgres_token, clean_env, caplog):
        """Test _build_connection_url with missing database."""
        clean_env(
            POSTGRES_HOST="localhost",
            POSTGRES_USER="testuser"
        )

        with caplog.at_level(logging.DEBUG):
            result = postgres_token._build_connection_url()

        assert result is None
        assert "POSTGRES_DB" in caplog.text

    def test_build_connection_url_missing_all(self, postgres_token, clean_env, caplog):
        """Test _build_connection_url with all components missing."""
        with caplog.at_level(logging.DEBUG):
            result = postgres_token._build_connection_url()

        assert result is None
        assert "POSTGRES_HOST" in caplog.text
        assert "POSTGRES_USER" in caplog.text
        assert "POSTGRES_DB" in caplog.text

    # get_connection_url tests

    def test_get_connection_url_from_env(self, postgres_token, clean_env, caplog):
        """Test get_connection_url from DATABASE_URL env var."""
        clean_env(DATABASE_URL="postgresql://user:pass@host:5432/db")

        with caplog.at_level(logging.DEBUG):
            result = postgres_token.get_connection_url()

        assert result == "postgresql://user:pass@host:5432/db"
        assert "Found URL in env var 'DATABASE_URL'" in caplog.text

    def test_get_connection_url_from_components(self, postgres_token, clean_env, caplog):
        """Test get_connection_url builds from individual components."""
        clean_env(
            POSTGRES_HOST="fallback-host",
            POSTGRES_USER="fallback-user",
            POSTGRES_DB="fallback-db"
        )

        with caplog.at_level(logging.DEBUG):
            result = postgres_token.get_connection_url()

        assert "fallback-host" in result
        # Implementation builds from components first (before checking DATABASE_URL)
        assert "Built URL from POSTGRES_* env vars" in caplog.text

    def test_get_connection_url_nothing_available(self, postgres_token, clean_env, caplog):
        """Test get_connection_url when nothing is available."""
        with caplog.at_level(logging.WARNING):
            result = postgres_token.get_connection_url()

        assert result is None
        assert "No connection URL available" in caplog.text
        # Implementation says "Set POSTGRES_HOST/USER/DB or DATABASE_URL"
        assert "POSTGRES_HOST" in caplog.text or "DATABASE_URL" in caplog.text

    def test_get_connection_url_custom_env_var(self, clean_env, caplog):
        """Test get_connection_url with custom env var config."""
        config = {
            "providers": {
                "postgres": {
                    "env_connection_url": "CUSTOM_DB_URL",
                }
            }
        }
        clean_env(CUSTOM_DB_URL="postgresql://custom:pass@host/db")
        mock_store = MockConfigStore(config)
        postgres_token = PostgresApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = postgres_token.get_connection_url()

        assert result == "postgresql://custom:pass@host/db"
        assert "CUSTOM_DB_URL" in caplog.text

    # get_api_key tests

    def test_get_api_key_with_url(self, postgres_token, clean_env, caplog):
        """Test get_api_key returns connection URL."""
        clean_env(DATABASE_URL="postgresql://user:pass@host/db")

        with caplog.at_level(logging.DEBUG):
            result = postgres_token.get_api_key()

        assert result.api_key == "postgresql://user:pass@host/db"
        assert result.auth_type == "connection_string"
        # Note: empty header_name gets defaulted to "Authorization" in ApiKeyResult
        assert result.header_name == "Authorization"
        assert result.has_credentials is True
        assert "Found connection URL" in caplog.text

    def test_get_api_key_without_url(self, postgres_token, clean_env, caplog):
        """Test get_api_key when no URL available."""
        with caplog.at_level(logging.WARNING):
            result = postgres_token.get_api_key()

        assert result.api_key is None
        assert result.auth_type == "connection_string"
        assert result.has_credentials is False
        assert "No connection URL available" in caplog.text

    # get_async_client tests

    @pytest.mark.asyncio
    async def test_get_async_client_no_asyncpg(self, postgres_token, clean_env, caplog):
        """Test get_async_client when asyncpg not installed."""
        from unittest.mock import patch

        with patch.dict("sys.modules", {"asyncpg": None}):
            with caplog.at_level(logging.WARNING):
                result = await postgres_token.get_async_client()

            assert result is None

    @pytest.mark.asyncio
    async def test_get_async_client_no_url(self, postgres_token, clean_env, caplog):
        """Test get_async_client when no connection URL or asyncpg not installed."""
        with caplog.at_level(logging.WARNING):
            result = await postgres_token.get_async_client()

        assert result is None
        # Either asyncpg not installed or no connection URL
        assert "asyncpg not installed" in caplog.text or "No connection URL available" in caplog.text

    # Validation tests
    def test_validate_with_url(self, postgres_token, clean_env):
        """Test validate with DATABASE_URL set."""
        clean_env(DATABASE_URL="postgresql://user:pass@host/db")

        result = postgres_token.validate()

        # Postgres has no base_url requirement
        assert result["has_credentials"] is True


class TestPostgresApiTokenEdgeCases:
    """Edge case tests for PostgresApiToken."""

    def test_connection_url_with_special_chars(self, clean_env):
        """Test connection URL with special characters in password."""
        clean_env(
            POSTGRES_HOST="localhost",
            POSTGRES_USER="testuser",
            POSTGRES_PASSWORD="p@ss:w0rd!",
            POSTGRES_DB="testdb"
        )

        config = {"providers": {"postgres": {}}}
        mock_store = MockConfigStore(config)
        postgres_token = PostgresApiToken(config_store=mock_store)

        result = postgres_token._build_connection_url()

        assert "p@ss:w0rd!" in result

    def test_connection_url_masked_in_logs(self, clean_env, caplog):
        """Test connection URL is masked in logs."""
        clean_env(DATABASE_URL="postgresql://user:secretpassword@host/db")

        config = {"providers": {"postgres": {}}}
        mock_store = MockConfigStore(config)
        postgres_token = PostgresApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            postgres_token.get_connection_url()

        # Verify password is not in plain text
        assert "secretpassword" not in caplog.text
        assert "masked=" in caplog.text

    def test_custom_port(self, clean_env):
        """Test custom port in connection URL."""
        clean_env(
            POSTGRES_HOST="localhost",
            POSTGRES_PORT="15432",
            POSTGRES_USER="testuser",
            POSTGRES_DB="testdb"
        )

        config = {"providers": {"postgres": {}}}
        mock_store = MockConfigStore(config)
        postgres_token = PostgresApiToken(config_store=mock_store)

        result = postgres_token._build_connection_url()

        assert ":15432/" in result
