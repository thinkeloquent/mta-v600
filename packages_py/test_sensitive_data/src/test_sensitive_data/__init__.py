"""
test_sensitive_data - Centralized sensitive test data for test suites.

This package provides a single source of truth for all test credentials,
tokens, PII data, and other sensitive information used in tests.

Example:
    from test_sensitive_data import get, get_all, has, get_many

    # Simple flat access
    email = get('email')
    password = get('password')

    # Dot notation for nested/categorized data
    confluence_email = get('credentials.confluence.email')
    jira_token = get('credentials.jira.token')

    # Check if a key exists
    if has('credentials.figma.token'):
        ...

    # Get multiple values at once
    email, password, api_key = get_many('email', 'password', 'api_key')

    # Get all data
    all_data = get_all()
"""

from .loader import (
    get,
    get_all,
    has,
    get_many,
    get_or_default,
    load_data,
    _reset_cache,
)

__all__ = [
    "get",
    "get_all",
    "has",
    "get_many",
    "get_or_default",
    "load_data",
    "_reset_cache",
]
