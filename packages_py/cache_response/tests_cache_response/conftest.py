"""Pytest configuration for cache_response tests."""
import pytest


@pytest.fixture
def sample_headers():
    """Sample response headers for testing."""
    return {
        "content-type": "application/json",
        "cache-control": "max-age=3600",
    }
