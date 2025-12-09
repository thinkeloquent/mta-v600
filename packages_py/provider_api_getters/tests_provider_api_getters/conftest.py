"""
Pytest configuration and shared fixtures for provider_api_getters tests.
"""
import logging
import os
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest


# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class MockConfigStore:
    """Mock ConfigStore for testing without actual static_config dependency."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._initialized = True

    def get(self, key: str, default: Any = None) -> Any:
        """Get a top-level config value."""
        return self._config.get(key, default)

    def get_nested(self, *keys: str, default: Any = None) -> Any:
        """Get a nested config value."""
        current = self._config
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    return default
            else:
                return default
        return current

    def is_initialized(self) -> bool:
        """Check if config is initialized."""
        return self._initialized

    def set_config(self, config: Dict[str, Any]) -> None:
        """Update the mock config."""
        self._config = config


@pytest.fixture
def mock_config_store():
    """Fixture that provides a mock config store."""
    return MockConfigStore()


@pytest.fixture
def figma_config():
    """Fixture with standard Figma provider configuration."""
    return {
        "providers": {
            "figma": {
                "base_url": "https://api.figma.com/v1",
                "env_api_key": "FIGMA_TOKEN",
            }
        }
    }


@pytest.fixture
def github_config():
    """Fixture with standard GitHub provider configuration."""
    return {
        "providers": {
            "github": {
                "base_url": "https://api.github.com",
                "env_api_key": "GITHUB_TOKEN",
            }
        }
    }


@pytest.fixture
def jira_config():
    """Fixture with standard Jira provider configuration."""
    return {
        "providers": {
            "jira": {
                "base_url": None,
                "env_api_key": "JIRA_API_TOKEN",
                "env_email": "JIRA_EMAIL",
                "health_endpoint": "/rest/api/2/myself",
            }
        }
    }


@pytest.fixture
def full_providers_config():
    """Fixture with all provider configurations."""
    return {
        "providers": {
            "figma": {
                "base_url": "https://api.figma.com/v1",
                "env_api_key": "FIGMA_TOKEN",
            },
            "github": {
                "base_url": "https://api.github.com",
                "env_api_key": "GITHUB_TOKEN",
            },
            "jira": {
                "base_url": None,
                "env_api_key": "JIRA_API_TOKEN",
                "env_email": "JIRA_EMAIL",
                "health_endpoint": "/rest/api/2/myself",
            },
            "confluence": {
                "base_url": None,
                "env_api_key": "CONFLUENCE_API_TOKEN",
                "env_email": "CONFLUENCE_EMAIL",
                "health_endpoint": "/wiki/rest/api/user/current",
            },
            "gemini": {
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                "env_api_key": "GEMINI_API_KEY",
            },
            "postgres": {
                "env_connection_url": "DATABASE_URL",
            },
            "redis": {
                "env_connection_url": "REDIS_URL",
            },
            "rally": {
                "placeholder": True,
                "message": "Rally integration not implemented",
            },
            "elasticsearch": {
                "placeholder": True,
                "message": "Elasticsearch integration not implemented",
            },
        }
    }


@pytest.fixture
def clean_env(monkeypatch):
    """
    Fixture that clears all provider-related environment variables.
    Returns a function to set environment variables for testing.
    """
    # List of env vars to clear
    env_vars_to_clear = [
        "FIGMA_TOKEN",
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "GITHUB_ACCESS_TOKEN",
        "GITHUB_PAT",
        "JIRA_API_TOKEN",
        "JIRA_EMAIL",
        "JIRA_BASE_URL",
        "CONFLUENCE_API_TOKEN",
        "CONFLUENCE_EMAIL",
        "CONFLUENCE_BASE_URL",
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "DATABASE_URL",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "POSTGRES_SSLMODE",
        "REDIS_URL",
        "REDIS_HOST",
        "REDIS_PORT",
        "REDIS_PASSWORD",
        "REDIS_DB",
        "REDIS_USERNAME",
        "REDIS_TLS",
    ]

    for var in env_vars_to_clear:
        monkeypatch.delenv(var, raising=False)

    def set_env(**kwargs):
        """Set environment variables for testing."""
        for key, value in kwargs.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)

    return set_env


@pytest.fixture
def assert_log_contains(caplog):
    """
    Fixture that provides a helper to assert log messages.
    Returns a function that checks if a log message contains expected text.
    """
    def _assert_log_contains(
        expected_text: str,
        level: Optional[str] = None,
        logger_name: Optional[str] = None
    ) -> bool:
        """
        Assert that logs contain expected text.

        Args:
            expected_text: Text that should appear in log messages
            level: Optional log level to filter (DEBUG, INFO, WARNING, ERROR)
            logger_name: Optional logger name to filter

        Returns:
            True if found, raises AssertionError otherwise
        """
        for record in caplog.records:
            if level and record.levelname != level:
                continue
            if logger_name and not record.name.startswith(logger_name):
                continue
            if expected_text in record.message:
                return True

        # Build helpful error message
        all_messages = [
            f"[{r.levelname}] {r.name}: {r.message}"
            for r in caplog.records
        ]
        raise AssertionError(
            f"Expected log containing '{expected_text}' not found.\n"
            f"Captured logs ({len(caplog.records)}):\n" +
            "\n".join(all_messages) if all_messages else "No logs captured"
        )

    return _assert_log_contains


@pytest.fixture
def count_log_occurrences(caplog):
    """
    Fixture that counts how many times a log message pattern appears.
    """
    def _count_log_occurrences(
        text: str,
        level: Optional[str] = None
    ) -> int:
        """Count log messages containing text."""
        count = 0
        for record in caplog.records:
            if level and record.levelname != level:
                continue
            if text in record.message:
                count += 1
        return count

    return _count_log_occurrences
